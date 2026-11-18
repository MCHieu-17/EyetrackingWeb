# Concurrency & resource utilization

Tài liệu này ghi lại các thay đổi tăng khả năng phục vụ đồng thời, cách đo lại,
và các nút thắt còn lại.

## Đã triển khai

### 1. Chat SSE không giữ DB connection

- `backend/app/api/routes/chat.py`: route chuẩn bị payload + lưu câu hỏi trong
  transaction ngắn, đóng `AsyncSession` trước khi trả `StreamingResponse`.
- `backend/app/services/study_chat.py`: `stream_in_session()` chỉ nhận
  `session_id`, `payload`, `ChatSessionSnapshot`; mở `SessionLocal()` ngắn khi
  lưu câu trả lời cuối.
- Kết quả đo: 10 chat stream đồng thời, `db_pool.checked_out = 0` trong suốt
  thời gian stream (trước đây mỗi stream giữ 1 connection).

### 2. Backend nhiều worker + pool nhỏ hơn

- `backend/Dockerfile`: `WEB_CONCURRENCY` (mặc định 2), chạy
  `uvicorn --workers`.
- `backend/app/core/config.py`: `DB_POOL_MIN=4`, `DB_POOL_MAX=10`,
  `DB_POOL_TIMEOUT=5`, `DB_STATEMENT_TIMEOUT_MS=15000`.
- `backend/app/db/session.py`: dùng các setting trên.
- `backend/app/main.py`: pool timeout trả `503` + `Retry-After` thay vì treo.

### 3. Postgres

- `shared_buffers=1GB`, `effective_cache_size=3GB`, `work_mem=16MB`,
  `maintenance_work_mem=256MB`, `max_connections=200`,
  `track_io_timing=on`, `idle_in_transaction_session_timeout=30s`.
- Postgres được cấp 4 CPU / 4GB RAM.

### 4. Redis cache + auth cache

- `backend/app/core/rediscache.py`: thêm `get_json`, `set_json`, `delete`
  (fail-open).
- `backend/app/crud/user.py`: `get_user_for_auth_cached()` cache
  id/status/deleted_at/roles trong 30s; invalidate khi đổi mật khẩu hoặc
  promote role.
- `GET /api/me/enrollments`: cache 30s theo user; invalidate khi thêm/bớt
  học viên.
- `GET /api/courses/{id}`: cache outline 60s theo course + published version +
  `updated_at`.

### 5. Nginx

- 2 worker, 8192 connection/worker, `keepalive_requests 1000`.
- `limit_req` cho `/api/` (20 r/s, burst 40) và `/api/auth/` (5 r/s, burst 10).
- `limit_conn` theo IP.
- Upstream `max_conns`, keepalive 64/32.
- `/_protected_media/` nội bộ: backend kiểm tra quyền rồi trả
  `X-Accel-Redirect`; nginx phục vụ file bằng `sendfile` + Range.

### 6. Frontend

- 2 replica Next standalone sau nginx (`FRONTEND_REPLICAS`, mặc định 2).
- Static assets vẫn được nginx cache 1 năm.

### 7. Gaze service

- **Thread cap theo CPU quota**: container gaze bị giới hạn `cpus: 2.0` nhưng
  OpenCV/torch/MediaPipe vẫn thấy toàn bộ core host → CFS throttling và stall
  ~80 ms/frame. `entrypoint.sh` set `OMP/MKL/OPENBLAS/NUMEXPR=1`; runtime gọi
  `cv2.setNumThreads(1)` + `torch.set_num_threads(1)` trước khi load model.
- Đo trên RTX 3060 (ảnh 512×512): full pipeline từ **55–85 ms p50 / 100–200 ms
  p95** xuống **10.9 ms p50 / 11.2 ms p95** (fp32). WebSocket 4 phiên @15 FPS
  từ **~16 FPS tổng** lên **~60 FPS tổng**; 8 phiên đạt **~115 FPS** (fp32);
  16 phiên đạt **~238 FPS** với fp16.
- **Pipeline 2 tầng**: CPU (decode/detect/warp) và GPU (UniGaze) chạy ở 2 thread
  riêng, queue 1 slot → overlap CPU/GPU, throughput ~1.5–1.8×.
- **Mailbox maxsize=1 + deadline**: receiver luôn giữ frame mới nhất; frame cũ
  hơn `FRAME_MAX_AGE_MS` (mặc định 200 ms) bị bỏ (`stale`). Queue đầy trả
  `overloaded` + `suggestedFps` ngay, không xếp hàng vô hạn.
- `MAX_QUEUE` (mặc định 8) thay cho `MAX_INFERENCE_QUEUE`; `INFER_WORKERS` đã
  bỏ vì MediaPipe không thread-safe và GPU serialize.
- `INFERENCE_PRECISION=fp32|fp16`: fp16 ~2.2× forward (8.45 → 3.79 ms trên
  3060), chỉ bật sau `scripts.compare_precision` đạt gate.
- Chạy **1 replica** mặc định (`GAZE_REPLICAS=1`) vì 1 GPU serialize; 2 replica
  chỉ tăng VRAM và cung cấp HA, không tăng throughput. Nếu dùng 2 replica,
  nginx vẫn giữ `hash $cookie_gaze_affinity` để session calibration nằm đúng
  process.
- Capacity tham khảo @15 FPS/phiên: ~7–8 phiên (fp32 + pipeline 2 tầng),
  ~15–16 phiên (fp16). Giảm `GAZE_FPS=10` tăng capacity ~1.5×.

### 8. Chatbot

- `CHATBOT_MAX_CONCURRENT` (mặc định 20): giới hạn số chat xử lý đồng thời.
- `CHATBOT_QUEUE_TIMEOUT` (mặc định 2s): quá thời gian chờ trả 429 +
  `Retry-After` thay vì xếp hàng vô hạn.
- Nhà cung cấp LLM vẫn là nút thắt bên ngoài; tăng `LLM_*` theo capacity thực tế.

### 9. Worker & retention

- Analysis worker chạy **2 replica** (`WORKER_REPLICAS`, mặc định 2; dùng
  `SKIP LOCKED`).
- `python -m app.maintenance` giờ:
  - schema generation 13 không còn partition; maintenance xoá `gaze_samples`
    cũ hơn `GAZE_RETENTION_DAYS` (mặc định 180 ngày) theo `event_time`.
- Có thể scale thêm content/embedding worker bằng `docker compose up -d
  --scale content-worker=2` khi cần (chú ý RAM LibreOffice).

### 10. PgBouncer (tùy chọn)

- Service `pgbouncer` nằm sau profile `pgbouncer`, không chạy mặc định.
- Bật khi scale backend > 4 worker:
  ```bash
  docker compose --profile pgbouncer up -d pgbouncer
  ```
- Đổi `DATABASE_URL_DOCKER` host sang `pgbouncer:5432`.
- Giữ `DB_PREPARED_STATEMENT_CACHE_SIZE=0` để tương thích transaction pooling.
- Migration vẫn chạy trực tiếp Postgres (không qua PgBouncer).

### 11. Metrics nội bộ

- `GET /internal/metrics` (chỉ gọi trực tiếp backend/localhost):
  DB pool, Redis, queue depth analysis/embedding/slide import.
- nginx đã chặn `/internal/` từ bên ngoài.

## Cách đo lại

```bash
# 1. Gate đầy đủ
./scripts/check.sh --full
./scripts/test_migrations.sh
./scripts/smoke.sh

# 2. Metrics nội bộ
curl -s http://localhost:8001/internal/metrics | python3 -m json.tool

# 3. Load test browse (k6 local hoặc Docker)
./scripts/loadtest.sh

# 4. Microbench endpoint
./scripts/bench.sh http://localhost:8001 /health

# 5. Initial JS theo route (sau npm run build)
node scripts/bundle-report.mjs

# 6. E2E smoke (stack phải đang chạy)
./scripts/e2e.sh
```

## Kết quả đo nhanh (dev stack)

| Test | Kết quả |
|---|---|
| 500 request đồng thời `/api/me/enrollments` (backend trực tiếp) | ~908 RPS, p95 462ms, 0 lỗi |
| 1000 request, concurrency 50 | ~955 RPS, p95 139ms, 0 lỗi |
| 10 chat stream đồng thời | DB pool `checked_out=0` trong suốt stream |
| Gaze batch hot path | 5 SQL query (từ 14 baseline) |
| Gaze pipeline (RTX 3060, 2 CPU, cap thread) | 10.9 ms p50 / 11.2 p95 (fp32) |
| Gaze WS 8 phiên @15 FPS (fp32) | ~115 response/s, ~14.3 FPS/phiên |
| Gaze WS 16 phiên @15 FPS (fp16) | ~238 response/s, ~14.9 FPS/phiên |
| Initial JS `/` (Turbopack manifest) | 169.7 KB |
| Initial JS `/student` | 299.1 KB |
| Initial JS `/teacher` | 283.8 KB |

Các số trên là đo trên máy dev, không phải cam kết production. Cần chạy
`loadtest.sh` trên staging với dữ liệu gần thật.

## Còn lại / follow-up

- **Gaze session state**: đã dùng cookie affinity để phân tải theo browser.
  Nếu cần chuyển session giữa replica (replica chết, đổi thiết bị), cần
  chuyển calibration state sang Redis.
- **Gaze throughput**: 1 GPU owner + pipeline 2 tầng. Nếu cần > 12–13 phiên
  @15 FPS/GPU, đo lại và cân nhắc TensorRT/ONNX hoặc thêm GPU; batching chỉ
  đáng khi chấp nhận thêm latency (b4 fp16 ~2.8 ms/frame so với 3.6 ms).
- **Chatbot**: đã có giới hạn concurrency + 429; nút thắt còn lại là quota
  nhà cung cấp LLM (`LLM_REQUESTS_PER_SECOND`). Có thể thêm cache retrieval/answer.
- **Worker**: analysis đã 2 replica; content/embedding có thể scale thêm khi
  backlog lớn (chú ý RAM LibreOffice).
- **Disk**: gaze đã có retention 180 ngày; vẫn cần retention log/backup và
  theo dõi dung lượng (ổ `/` còn ~13GB).
- **PgBouncer**: đã sẵn sàng sau profile `pgbouncer`; bật khi scale backend
  > 4 worker.
