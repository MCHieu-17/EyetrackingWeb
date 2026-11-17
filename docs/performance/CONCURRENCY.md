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

- `MAX_INFERENCE_QUEUE` (mặc định 32): queue đầy trả `overloaded` thay vì phình
  vô hạn.
- `GAZE_FPS` (mặc định 15): throttle mỗi session = `1000/FPS × 0.95`; tăng FPS
  làm tăng tải suy luận/GPU mỗi session. FPS cao hơn nghĩa là nhiều frame phải
  inference hơn — cân nhắc `INFER_WORKERS`/`MAX_INFERENCE_QUEUE` tương ứng.
- Calibration trả 503 + `Retry-After` khi queue đầy; WebSocket trả trạng thái
  `overloaded` và giữ stream.
- Chạy **2 replica** gaze sau nginx (`GAZE_REPLICAS`, mặc định 2). Frontend
  tạo cookie `gaze_affinity` trước request đầu; nginx dùng
  `hash $cookie_gaze_affinity` giữ mọi request/WS của cùng browser trên một
  replica vì session calibration nằm trong RAM.
- Nếu không có cookie, mọi request hash rỗng nên vẫn về cùng một replica
  (đúng, nhưng không phân tải). Xoá cookie giữa phiên sẽ mất session và phải
  calibration lại.

### 8. Chatbot

- `CHATBOT_MAX_CONCURRENT` (mặc định 20): giới hạn số chat xử lý đồng thời.
- `CHATBOT_QUEUE_TIMEOUT` (mặc định 2s): quá thời gian chờ trả 429 +
  `Retry-After` thay vì xếp hàng vô hạn.
- NEU vẫn là nút thắt bên ngoài; tăng `NEU_*` theo capacity thực tế.

### 9. Worker & retention

- Analysis worker chạy **2 replica** (`WORKER_REPLICAS`, mặc định 2; dùng
  `SKIP LOCKED`).
- `python -m app.maintenance` giờ:
  - schema generation 12 không còn partition; maintenance xoá `gaze_samples`
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
| Gaze queue 40 task, queue limit 32 | 32 ok, 8 overloaded (đúng thiết kế) |
| Initial JS `/` (Turbopack manifest) | 169.7 KB |
| Initial JS `/student` | 299.1 KB |
| Initial JS `/teacher` | 283.8 KB |

Các số trên là đo trên máy dev, không phải cam kết production. Cần chạy
`loadtest.sh` trên staging với dữ liệu gần thật.

## Còn lại / follow-up

- **Gaze session state**: đã dùng cookie affinity để phân tải theo browser.
  Nếu cần chuyển session giữa replica (replica chết, đổi thiết bị), cần
  chuyển calibration state sang Redis.
- **Gaze throughput**: vẫn 1 inference worker/GPU mỗi replica. Nếu cần
  > 100 stream đồng thời, đo GPU rồi cân nhắc TensorRT/ONNX hoặc thêm GPU.
- **Chatbot**: đã có giới hạn concurrency + 429; nút thắt còn lại là quota
  NEU (`NEU_REQUESTS_PER_SECOND`). Có thể thêm cache retrieval/answer.
- **Worker**: analysis đã 2 replica; content/embedding có thể scale thêm khi
  backlog lớn (chú ý RAM LibreOffice).
- **Disk**: gaze đã có retention 180 ngày; vẫn cần retention log/backup và
  theo dõi dung lượng (ổ `/` còn ~13GB).
- **PgBouncer**: đã sẵn sàng sau profile `pgbouncer`; bật khi scale backend
  > 4 worker.
