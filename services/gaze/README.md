# Gaze service

FastAPI service ước lượng hướng nhìn từ webcam. Đây là service **duy nhất cần
GPU** trong stack mặc định; chatbot embedding chạy CPU.

## Kiến trúc

```text
WebSocket (per session)
  receiver task: đọc frame, throttle GAZE_FPS, mailbox maxsize=1
  processor task: lấy frame mới nhất -> pipeline -> send queue
  sender task: gửi response (client chậm không chặn pipeline)

Pipeline 2 tầng (2 thread riêng)
  CPU: decode JPEG -> MediaPipe detect -> warp 224x224
       -> queue GPU_QUEUE slot ->
  GPU: gom tối đa GPU_BATCH frame/forward -> normalize -> UniGaze
       -> calibration -> One-Euro -> (x, y)
```

- Mỗi session chỉ có tối đa 1 frame trong pipeline → không lệch thứ tự.
- Frame cũ hơn `FRAME_MAX_AGE_MS` bị bỏ (`stale`) thay vì inference.
- Queue đầy → trả `overloaded` ngay, kèm `suggestedFps`.
- GPU gom frame của nhiều session vào một forward; `GPU_QUEUE` phải ≥
  `GPU_BATCH` để batch lớn có thể hình thành.
- Calibration nằm trong RAM và mất khi container restart. Backend lưu model
  `.ubj` trong `gaze_calibrations` để frontend import lại.

### Vì sao cap thread?

Container gaze bị giới hạn CPU (mặc định `cpus: 2.0`) nhưng OpenCV/torch/
MediaPipe vẫn thấy toàn bộ core của host. Oversubscription gây CFS throttling
và stall ~80 ms/frame. Service cap `cv2`/`torch` về 1 thread trong code và
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
| `WEIGHTS_DIR` | `/app/weights` | Volume weights runtime |
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
`cv2.setNumThreads(1)` và `torch.set_num_threads(1)` được gọi trong runtime.

## Capacity (RTX 3060, 1 GPU, 15 FPS/phiên)

| Cấu hình | FPS/GPU | Phiên @15 FPS |
|---|---:|---:|
| Không cap thread | ~16 | ~1 |
| Cap thread + pipeline 2 tầng (fp32) | ~115 | ~7–8 |
| + fp16 + batch 8 | ~395 (batch 8) | ~16 (CPU stage ~240 fps) |

Đo trên RTX 3060 (container 2 CPU, ảnh 480px, fp16, `GPU_BATCH=8`,
`GPU_QUEUE=12`): 8 phiên @15 FPS đạt 120 response/s, p95 ~19 ms; 16 phiên
(2 tiến trình client × 8) đạt 240 response/s, p95 ~51 ms, 97,7% frame `ok`.
Nút cổ chai còn lại là CPU stage (~4,1 ms/frame) chứ không phải GPU.
Giảm `GAZE_FPS` xuống 10 sẽ tăng capacity ~1.5× (worker vẫn tính đúng gap
threshold vì suy ra từ `GAZE_FPS`).

## Lint

```bash
cd services/gaze
.venv/bin/ruff check app
```

## Test

```bash
./scripts/test_gaze.sh fast    # HTTP/WS + Linear Regression, runtime giả
./scripts/test_gaze.sh smoke   # MediaPipe + UniGaze thật trên ảnh mẫu
```

Smoke cần weights trong `gaze-weights`; chạy CPU được nhưng chậm hơn GPU.
Ảnh mẫu và nguồn/license: `tests/fixtures/README.md`.

## Bench & validate fp16

```bash
# Cần ảnh JPEG/PNG có mặt người
docker compose exec -T gaze python -m scripts.bench \
  --image /tmp/face.jpg --sessions 1,4,8,12 --fps 15 --duration 10

# So sánh fp32 vs fp16 trên thư mục ảnh; exit 1 nếu vượt gate
docker compose exec -T gaze python -m scripts.compare_precision \
  --dir /tmp/faces --max-mean-deg 0.05 --max-abs-deg 0.3
```

fp16 là mặc định sau A/B trên `unigaze_b16_joint`. Khi đổi model/GPU hoặc chạy
CPU, đặt `INFERENCE_PRECISION=fp32`; hạ `GAZE_GPU_BATCH=2` nếu cần giữ VRAM.
Batch forward được đo trong `benchmarks/gaze/stage_latency.py` (khối `batch`).

## Đổi backbone UniGaze

Model được chọn tường minh bằng `UNIGAZE_MODEL` trong `.env` (local) hoặc
`stack.env` (production); không hardcode trong code. Khi đổi model:

1. Đổi `UNIGAZE_MODEL` sang một trong các tên hỗ trợ.
2. Recreate service gaze để entrypoint tải weights mới vào volume.
3. Đổi `MAPPING_MODEL_VERSION` trong `backend/app/api/routes/calibration.py`.
4. Buộc người dùng calibration lại; model cũ sẽ trả 409 ở
   `/api/calibrations/active/model`.

`DEVICE` cũng bắt buộc đặt tường minh (`cpu`/`cuda`); service không tự dò GPU.
MediaPipe face detector là ngoại lệ: luôn chạy CPU và dùng model cố định.
