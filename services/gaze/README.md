# Gaze service

FastAPI service ước lượng hướng nhìn từ webcam. Đây là service **duy nhất cần
GPU** trong stack mặc định; chatbot embedding chạy CPU.

## Kiến trúc

```text
JPEG frame
  → MediaPipe face detection
  → UniGaze (pitch, yaw)
  → calibration hồi quy tuyến tính
  → (x, y) chuẩn hóa theo viewport
  → One-Euro smoothing
```

Session calibration nằm trong RAM và mất khi container restart. Backend lưu
model `.ubj` trong `gaze_calibrations` để frontend import lại.

## Chạy

Trong stack:

```bash
docker compose up -d --build gaze
docker compose logs -f gaze
```

Gaze không publish cổng host trong compose mặc định (2 replica dùng chung GPU).
Browser truy cập qua nginx `/gaze/*`; debug trực tiếp bằng:

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
| GET | `/health` | Liveness; 200 khi process còn sống |
| GET | `/ready` | Readiness; 503 khi MediaPipe/UniGaze chưa load |
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

Tối đa 64 điểm/session, ID không trùng. `POST /session` trả
`{"session_id": "..."}` và 503 khi vượt `MAX_SESSIONS`.

### Thu mẫu và train

`POST /session/{sid}/calibrate` nhận multipart:

- `image`: JPEG;
- `point_id`: ID đã khai báo.

HTTP 200 có thể mang `status`:

- `accepted`: đã lưu mẫu;
- `no_face`: không detect được mặt;
- `invalid_image`: JPEG hỏng;
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

Server echo lại `frameId`, `sequence`, `captureMonotonicNs`,
`presentationId`, `layoutGeneration` trong response. Response thành công:

```json
{"ok":true,"status":"ok","x":0.52,"y":0.34,"frameId":"uuid","sequence":12}
```

Khi lỗi:

```json
{"ok":false,"status":"no_face","error":"no_face","frameId":"uuid","sequence":13}
```

Các giá trị `status`/`error`:

- `no_face`: frame không có mặt;
- `invalid_image`: frame hỏng;
- `internal`: lỗi suy luận một frame, stream vẫn tiếp tục;
- `overloaded`: queue suy luận đầy, client nên giảm FPS.

JPEG legacy không có header vẫn được chấp nhận, nhưng không có metadata echo.
Frame bị drop nếu session đang xử lý frame trước hoặc gửi dày hơn
`MIN_FRAME_INTERVAL_MS` (mặc định 80 ms, khoảng 12.5 FPS).

WebSocket close:

- `1008 not_calibrated`: session chưa train/import;
- `1013 pipeline_not_ready`: model chưa load xong.

## Tọa độ và viewport

- Gaze trả `[0,1]` theo **viewport lúc calibration**.
- Giá trị có thể âm hoặc > 1 khi người dùng nhìn ra ngoài màn hình.
- Frontend quy đổi từ viewport calibration sang viewport hiện tại bằng
  `innerWidth/innerHeight`, `screenX/screenY`, DPR. Vì vậy zoom/resize/move cửa
  sổ không cần calibration lại.
- Backend lưu gaze thô theo viewport; worker mới quy đổi sang slide/AOI.

## Cấu hình chính

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `DEVICE` | **bắt buộc** | `cuda` hoặc `cpu`; thiếu/sai → fail-fast |
| `UNIGAZE_MODEL` | **bắt buộc** | `unigaze_b16_joint` \| `unigaze_l16_joint` \| `unigaze_h14_joint` \| `unigaze_h14_cross_X` |
| `WEIGHTS_DIR` | `/app/weights` | Volume weights runtime |
| `MAX_SESSIONS` | `100` | Session đồng thời |
| `SESSION_TTL_SECONDS` | `1800` | TTL session không hoạt động |
| `MAX_POINTS` | `64` | Điểm calibration tối đa |
| `MAX_SAMPLES_PER_POINT` | `50` | Mẫu giữ lại/point |
| `GAZE_MAX_UPLOAD_BYTES` → `MAX_UPLOAD_BYTES` | `5242880` | Ảnh upload tối đa |
| `MAX_INFERENCE_QUEUE` | `32` | Queue suy luận |
| `MIN_FRAME_INTERVAL_MS` | `80` | Throttle FPS mỗi session |
| `ONEEURO_*` | `0.5/0.5/1.0` | Bộ lọc làm mượt |

## Test

```bash
cd services/gaze
.venv/bin/python -m pytest -q
.venv/bin/ruff check app tests
```

Test hiện có bao phủ protocol v2/legacy, calibration `.ubj`, One-Euro filter,
TTL/giới hạn session và giữ mẫu. Test inference đầy đủ cần image có
MediaPipe/UniGaze/GPU.

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
