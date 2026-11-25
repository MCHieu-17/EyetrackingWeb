# Gaze service

FastAPI service ước lượng hướng nhìn từ webcam. Đây là service **duy nhất cần
GPU** trong stack mặc định; chatbot embedding chạy CPU.

## Kiến trúc

```text
WebSocket (per session)
  receiver task: đọc frame, throttle GAZE_FPS, mailbox maxsize=1
  processor task: lấy frame mới nhất -> pipeline -> send queue
  sender task: gửi response (client chậm không chặn pipeline)

Pipeline 2 tầng (CPU_WORKERS thread CPU + 1 thread GPU)
  CPU thread: decode JPEG -> FaceLandmarker ONNX (BlazeFace 128 + mạng 478 điểm,
       chạy trên GPU bằng CUDA EP, session riêng mỗi thread) -> bbox x2 + 6 điểm (iBUG)
       -> solvePnP -> warp 224x224 (RGB uint8) + ma trận xoay R
       -> queue GPU_QUEUE slot ->
  GPU: gom tối đa GPU_BATCH frame/forward -> UniGaze ONNX (onnxruntime,
       chuẩn hoá ImageNet nằm trong graph) -> denormalize bằng R
       -> calibration -> One-Euro -> (x, y)

Runtime KHÔNG có torch và KHÔNG có mediapipe. Service một-lần `gaze-export` (target
Docker `export`, có torch + mediapipe + tflite) ghi vào volume `gaze-weights`:
- UniGaze: `<model>.fp32.onnx`, `<model>.fp16.onnx` (+ manifest `.onnx.json`);
- FaceLandmarker: `face_detector.onnx`, `face_landmarks.onnx` (fp32, convert từ
  `face_landmarker.task` bằng `scripts/tflite_to_onnx.py`; `export_landmarker.py`).
Số học tiền/hậu xử lý landmarker (anchor, NMS, ROI xoay, chiếu) nằm ở
`app/services/landmarker.py` và tái hiện MediaPipe chế độ IMAGE.
```

- Mỗi session chỉ có tối đa 1 frame trong pipeline → không lệch thứ tự.
- Frame cũ hơn `FRAME_MAX_AGE_MS` bị bỏ (`stale`) thay vì inference.
- Queue đầy → trả `overloaded` ngay, kèm `suggestedFps`.
- GPU gom frame của nhiều session vào một forward; `GPU_QUEUE` phải ≥
  `GPU_BATCH` để batch lớn có thể hình thành.
- Calibration nằm trong RAM và mất khi container restart. Backend lưu model
  `.ubj` trong `gaze_calibrations` để frontend import lại.

### Vì sao cap thread?

Container gaze bị giới hạn CPU (mặc định `cpus: 4.0`) nhưng OpenCV/
onnxruntime vẫn thấy toàn bộ core của host. Oversubscription gây CFS throttling
và stall ~80 ms/frame. Service cap `cv2`/OpenMP về 1 thread trong code và
`entrypoint.sh` export `OMP/MKL/OPENBLAS/NUMEXPR=1`.

Đo trên RTX 3060 (container 2 CPU, ảnh 512×512):

| Cấu hình | Full pipeline p50 | p95 |
|---|---:|---:|
| Không cap thread | 55–85 ms | 100–200 ms |
| Có cap thread (fp32) | **10.9 ms** | **11.2 ms** |
| Có cap thread (fp16) | **6,6 ms** | **7,0 ms** |

## Chạy

Trong stack:

```bash
docker compose up -d --build gaze
docker compose logs -f gaze
```

Gaze không publish cổng host trong compose mặc định. Browser truy cập qua nginx
`/gaze/*`; debug trực tiếp bằng:

```bash
docker compose exec gaze python -c \
  "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/ready').read())"
```

Khi chạy riêng trên host:

```bash
cd services/gaze
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m uvicorn app.main:app --port 8000
```

`DEVICE=cpu` chạy được nhưng rất chậm và không phù hợp để dùng thật.

## HTTP API

| Method | Path | Ý nghĩa |
|---|---|---|
| GET | `/health` | Liveness + `device/model/precision/stats/queue/sessions` |
| GET | `/ready` | Readiness; 503 khi pipeline chưa load/warmup xong |
| POST | `/session` | Tạo session và khai báo các điểm calibration |
| GET | `/session/{sid}` | Trạng thái `collecting` hoặc `ready` |
| DELETE | `/session/{sid}` | Giải phóng session |
| POST | `/session/{sid}/calibrate` | Gửi một ảnh JPEG + `point_id` |
| POST | `/session/{sid}/train` | Fit model từ các mẫu đã thu |
| GET | `/session/{sid}/model` | Tải model `.ubj` v2 |
| POST | `/session/{sid}/import` | Nạp model `.ubj` đã lưu |
| WS | `/session/{sid}/stream` | Gửi frame, nhận tọa độ gaze |

### Tạo session

```json
{
  "points": [
    {"id": "c", "x": 0.5, "y": 0.5},
    {"id": "tl", "x": 0.125, "y": 0.167}
  ]
}
```

Tối đa 64 điểm/session (và `MAX_POINTS`), ID không trùng. `POST /session` trả
`{"session_id": "..."}` và 503 khi vượt `MAX_SESSIONS`.

### Thu mẫu và train

`POST /session/{sid}/calibrate` nhận multipart:

- `image`: JPEG;
- `point_id`: ID đã khai báo.

HTTP 200 có thể mang `status`:

- `accepted`: đã lưu mẫu;
- `no_face`: không detect được mặt;
- `invalid_image`: JPEG hỏng/quá lớn;
- `unknown_point`: point ID sai.

`POST /session/{sid}/train` trả `{"status":"ok","n_samples":N}`. Nếu thiếu mẫu,
trả 422 với `detail` là map `point_id → số mẫu`.

Model `.ubj` v2 chỉ chứa hệ số, không dùng pickle:

```json
{"format":"gaze-lr-v2","coef":[[a1,a3],[a2,a4]],"intercept":[b1,b2]}
```

Model sai format/shape hoặc dùng format cũ trả `invalid_model` khi import.

### WebSocket protocol v2

Client gửi binary message:

```text
[4-byte big-endian header length][JSON header UTF-8][JPEG bytes]
```

Header:

```json
{
  "v": 2,
  "frameId": "uuid",
  "sequence": 12,
  "captureMonotonicNs": 123456789,
  "eventTime": "2026-11-13T10:00:00.000Z",
  "presentationId": "content-view-id",
  "layoutGeneration": 3,
  "surface": "lesson",
  "viewportWidth": 1280,
  "viewportHeight": 720,
  "dpr": 1
}
```

Server echo lại `frameId`, `sequence`, `captureMonotonicNs`, `eventTime`,
`presentationId`, `layoutGeneration` trong response. Response thành công:

```json
{"ok":true,"status":"ok","x":0.52,"y":0.34,"frameId":"uuid","sequence":12}
```

Khi lỗi:

```json
{"ok":false,"status":"no_face","error":"no_face","frameId":"uuid","sequence":13}
```

Các giá trị `status`/`error`:

- `no_face`: frame không có mặt (hoặc tư thế đầu vượt ngưỡng);
- `invalid_image`: frame hỏng/quá `MAX_FRAME_BYTES`;
- `stale`: frame chờ quá `FRAME_MAX_AGE_MS`, bị bỏ để giữ latency;
- `overloaded`: queue đầy; response kèm `suggestedFps`;
- `internal`: lỗi suy luận một frame, stream vẫn tiếp tục.

JPEG legacy không có header vẫn được chấp nhận, nhưng không có metadata echo.
Frame bị drop nếu session đang xử lý frame trước, gửi dày hơn `GAZE_FPS`
(throttle = `1000/FPS × 0.85` ms), hoặc bị frame mới hơn thay thế trong mailbox.

WebSocket close:

- `1008 not_calibrated`: session chưa train/import;
- `1013 pipeline_not_ready`: model chưa load xong.

## Tọa độ và viewport

- Gaze trả `[0,1]` theo **viewport lúc calibration**.
- Giá trị có thể âm hoặc > 1 khi người dùng nhìn ra ngoài màn hình.
- Frontend quy đổi từ viewport calibration sang viewport hiện tại bằng
  `innerWidth/innerHeight`, `screenX/screenY`, DPR. Zoom/resize/move cửa sổ
  không cần calibration lại.
- Backend lưu gaze thô theo viewport; worker mới quy đổi sang slide/AOI.

## Cấu hình chính

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `DEVICE` | **bắt buộc** | `cuda` hoặc `cpu`; thiếu/sai → fail-fast |
| `UNIGAZE_MODEL` | **bắt buộc** | `unigaze_b16_joint` \| `unigaze_l16_joint` \| `unigaze_h14_joint` \| `unigaze_h14_cross_X` |
| `INFERENCE_PRECISION` | `fp16` | `fp32` \| `fp16`; mặc định sau A/B trên `unigaze_b16_joint`; đặt `fp32` khi đổi model/GPU hoặc chạy CPU |
| `CPU_WORKERS` | `2` | Số thread CPU stage (decode + landmarker ONNX ~10 ms/frame/thread khi tải thật); 1..8 |
| `WEIGHTS_DIR` | `/app/weights` | Volume weights runtime (`face_landmarker.task` chỉ để export, `*.onnx`) |
| `MAX_SESSIONS` | `100` | Session đồng thời |
| `SESSION_TTL_SECONDS` | `1800` | TTL session không hoạt động |
| `MAX_POINTS` | `64` | Điểm calibration tối đa |
| `MAX_SAMPLES_PER_POINT` | `50` | Mẫu giữ lại/point |
| `GAZE_MAX_UPLOAD_BYTES` → `MAX_UPLOAD_BYTES` | `5242880` | Ảnh calibration/import tối đa |
| `MAX_FRAME_BYTES` | `1048576` | JPEG tối đa cho 1 frame WS |
| `MAX_QUEUE` | `8` | Số frame chờ trong queue CPU |
| `GPU_QUEUE` | `12` | Số frame chờ trong queue GPU |
| `GPU_BATCH` | `8` | Số frame gộp trong một forward (cần `GPU_QUEUE ≥ GPU_BATCH`) |
| `FRAME_MAX_AGE_MS` | `200` | Tuổi tối đa trước khi drop `stale` |
| `INFERENCE_TIMEOUT_S` | `5` | Timeout 1 job suy luận |
| `GAZE_FPS` | `15` | Frame/giây trình duyệt gửi; throttle = `1000/FPS × 0.85` |
| `ONEEURO_*` | `0.5/0.5/1.0` | Bộ lọc làm mượt |

Thread cap (`OMP/MKL/OPENBLAS/NUMEXPR=1`) được `entrypoint.sh` set mặc định;
`cv2.setNumThreads(1)` được gọi trong runtime; song song hoá CPU stage bằng `CPU_WORKERS`
(mỗi thread có một bộ session landmarker riêng).

## Capacity (RTX 3060, 1 GPU, 15 FPS/phiên)

Đo bằng `benchmarks/gaze/standalone.sh` (ảnh 480px, fp16, `GPU_BATCH=8`). Kết quả:
`benchmarks/baseline/post-landmarker-onnx/` (so với `post-onnx/` và `pre-onnx/`).

| Chỉ số | BlazeFace + torch | FaceLandmarker MediaPipe CPU | Landmarker ONNX GPU |
|---|---:|---:|---:|
| CPU stage / frame (mean, ảnh 480px) | 2,84 ms | 13,8 ms | 4,5 ms |
| Tổng stage p50 / p95 | – | 16,2 / 28,6 ms | 7,5 / 7,9 ms |
| 8 phiên @15 FPS: drop / RTT p95 (4 core) | 0% / 41 ms | 0,14% / 57 ms | 0% / 43 ms |
| 8 phiên với `cpus: 2.0`, 2 worker: drop / RTT p95 | – | >30% | 0% / 44 ms |
| 12 phiên: `overloaded` | 523/5400 | 700/5400 | 129/5400 |
| Image gaze | 10,2 GB | 7,2 GB | 6,3 GB |

`cpus: 2.0` + `CPU_WORKERS=2` đủ 8 phiên @15 FPS. 12 phiên bắt đầu `overloaded` (GPU
thread và 2 core là giới hạn). Giảm `GAZE_FPS` tăng capacity tương ứng (worker vẫn tính
đúng gap threshold vì suy ra từ `GAZE_FPS`).

## Lint

```bash
cd services/gaze
.venv/bin/ruff check app
```

## Test

```bash
./scripts/test_gaze.sh fast    # HTTP/WS + Linear Regression, runtime giả
./scripts/test_gaze.sh smoke   # landmarker ONNX (golden MediaPipe) + UniGaze ONNX thật trên ảnh mẫu
```

Smoke cần weights trong `gaze-weights`; chạy CPU được nhưng chậm hơn GPU.
Ảnh mẫu và nguồn/license: `tests/fixtures/README.md`.

## Bench & validate fp16

Script đo nằm ở `benchmarks/gaze/` chứ không nằm trong image runtime: mount thư mục
`benchmarks` vào `/bench` rồi gọi trực tiếp đường dẫn script (`--entrypoint python`
để bỏ entrypoint uvicorn; thêm `--user root` nếu ghi kết quả ra thư mục của host).

```bash
# Cần ảnh JPEG/PNG có mặt người
docker compose run --rm --no-deps --entrypoint python \
  -v "$PWD/benchmarks":/bench gaze /bench/gaze/tools/bench.py \
  --image /tmp/face.jpg --sessions 1,4,8,12 --fps 15 --duration 10

# So sánh fp32 vs fp16 trên thư mục ảnh; exit 1 nếu vượt gate
docker compose run --rm --no-deps --entrypoint python \
  -v "$PWD/benchmarks":/bench gaze /bench/gaze/tools/compare_precision.py \
  --dir /tmp/faces --max-mean-deg 0.05 --max-abs-deg 0.3
```

fp16 (ONNX) là mặc định. `DEVICE=cpu` nên dùng `INFERENCE_PRECISION=fp32`; hạ `GPU_BATCH=2` nếu cần giữ VRAM.
Batch forward được đo trong `benchmarks/gaze/stage_latency.py` (khối `batch`).
Độ chính xác offline (100 target) đo bằng `benchmarks/gaze/tools/eval_offline.py`,
ảnh mẫu giữ ở `benchmarks/gaze/testdata/` (gitignored).

## Đổi backbone UniGaze

Model được chọn tường minh bằng `UNIGAZE_MODEL` trong `.env` (local) hoặc
`stack.env` (production); không hardcode trong code. Khi đổi model:

1. Đổi `UNIGAZE_MODEL` sang một trong các tên hỗ trợ.
2. Chạy lại `docker compose run --rm gaze-export` (tải safetensors + export ONNX),
   rồi recreate service gaze.
3. Đổi `MAPPING_MODEL_VERSION` trong `backend/app/api/routes/calibration.py`.
4. Buộc người dùng calibration lại; model cũ sẽ trả 409 ở
   `/api/calibrations/active/model`.

`DEVICE` cũng bắt buộc đặt tường minh (`cpu`/`cuda`); service không tự dò GPU.
Landmarker ONNX dùng chung `DEVICE` (CUDA EP khi `cuda`, CPU EP khi `cpu`) và model cố
định (`face_landmarker.task`, kiểm tra sha256 khi tải, chỉ để export).

## Đổi pipeline và calibration cũ

Pipeline hiện tại (FaceLandmarker 478 điểm + tiền xử lý/denormalize theo nghiên cứu
gốc, mô tả ở `docs/gaze/architecture.md`) sinh `(pitch, yaw)` ở hệ quy chiếu khác pipeline
cũ (BlazeFace + torch). Migration `007_reset_gaze_calibrations.sql` xoá mọi calibration
đã lưu và `MAPPING_MODEL_VERSION` là `ubj-linreg-v3-*`: học viên phải calibration lại.
Rollback = dùng lại tag image cũ (`pre-onnx`) **và** không có đường quay lại calibration
đã xoá; hãy backup DB trước khi deploy (`./scripts/backup.sh`).
