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

- 2 replica Next standalone sau nginx (`deploy.replicas: 2`).
- Static assets vẫn được nginx cache 1 năm.

### 7. Gaze service

- `MAX_INFERENCE_QUEUE` (mặc định 32): queue đầy trả `overloaded` thay vì phình
  vô hạn.
- `MIN_FRAME_INTERVAL_MS` (mặc định 80ms): giới hạn ~12.5 FPS/session.
- Calibration trả 503 + `Retry-After` khi queue đầy; WebSocket trả trạng thái
  `overloaded` và giữ stream.

### 8. Metrics nội bộ

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
```

## Kết quả đo nhanh (dev stack)

| Test | Kết quả |
|---|---|
| 500 request đồng thời `/api/me/enrollments` (backend trực tiếp) | ~908 RPS, p95 462ms, 0 lỗi |
| 1000 request, concurrency 50 | ~955 RPS, p95 139ms, 0 lỗi |
| 10 chat stream đồng thời | DB pool `checked_out=0` trong suốt stream |
| Gaze queue 40 task, queue limit 32 | 32 ok, 8 overloaded (đúng thiết kế) |

Các số trên là đo trên máy dev, không phải cam kết production. Cần chạy
`loadtest.sh` trên staging với dữ liệu gần thật.

## Còn lại / follow-up

- **PgBouncer**: hiện tổng connection dự kiến ~60–80, dưới `max_connections=200`.
  Chỉ cần PgBouncer khi scale backend > 4 worker hoặc thêm nhiều worker.
- **Gaze**: vẫn 1 inference worker/GPU. Nếu cần > 50–100 stream đồng thời, đo
  GPU utilization rồi cân nhắc 2 replica + sticky session hoặc TensorRT/ONNX.
- **Chatbot**: nút thắt là River API (`RIVER_REQUESTS_PER_SECOND`, semaphore).
  Cần queue ưu tiên + cache retrieval/answer + tăng quota nếu có.
- **Worker**: có thể scale analysis/content/embedding bằng `docker compose
  up -d --scale worker=2` (các job đã dùng `SKIP LOCKED`).
- **Disk**: ổ `/` còn ~13GB; cần retention gaze/log/backup trước khi chạy tải
  lớn thời gian dài.
