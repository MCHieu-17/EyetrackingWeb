# Perf audit — Phần 1: Backend & DB

> Phạm vi: FastAPI (router → middleware → dependency auth → service → SQLAlchemy/Redis → response), các worker backend, và phần giao tiếp sang chatbot/gaze ở phía backend.
> Nguồn: code hiện tại, `benchmarks/baseline/20261120T180000Z-baseline/` (k6 + `pg_stat_statements` + EXPLAIN), và đo trực tiếp trên stack dev.
> Không sửa code. Các số đo local chỉ để xác định bậc độ lớn; baseline benchmark có dataset nhỏ hơn production.

## 0. Vòng đời request đã trace

```text
Browser
  → nginx :3000            limit_req api_rl 20 r/s, limit_conn perip_api 30–50, rewrite /api/teacher|admin
  → FastAPI middleware      request_timing: perf_counter + Server-Timing + log nếu >= 250 ms
  → Depends(require_roles)  get_current_user → Redis GET auth:user:* (30 s) → miss mới query users
  → Depends(get_db)         AsyncSession từ pool 4–10/worker, pool_pre_ping (SELECT 1)
  → route (mỏng)            validate + gọi service
  → service                 SQLAlchemy async → asyncpg → PostgreSQL; Redis cache/rate-limit
        ├─ chat:  httpx AsyncClient → chatbot :8000 → (chatbot gọi ngược backend /internal/chat/lms-query)
        │          → query rewrite LLM → embedding CPU → FTS/pgvector → generation SSE
        └─ gaze:  WS → gaze :8000 → CPU thread (decode/MediaPipe) → GPU thread (UniGaze/calibration)
  → response_model          Pydantic v2 → jsonable_encoder → JSONResponse
```

Các endpoint nóng lấy từ baseline (k6, 2–5 VU):

| Endpoint | p50 | p95 | rps | queries/request (thô*) |
|---|---:|---:|---:|---:|
| `POST /teacher/courses/{id}/analytics/aoi-summary` | **1249 ms** | 1308 ms | 1.38 | 13.7 |
| `GET /teacher/visits/{id}/replay` | 53.4 ms | 60.5 ms | 7.96 | 15.25 |
| `POST /api/learning-sessions/{id}/gaze-batches` | 36.2 ms | 53.1 ms | 7.69 | — |
| `GET /teacher/courses/{id}/visits` | 35.6 ms | 70.8 ms | 20.7 | 9.2 |
| `GET /teacher/courses` | 33.4 ms | 45.5 ms | 8.57 | 9.25 |
| `GET /teacher/visits/{id}/samples` | 18.3 ms | 30.5 ms | 22.6 | 11.2 |
| `GET /api/lessons/{id}/contents` | 16.8 ms | 34.5 ms | 22.8 | — |
| `GET /api/courses/{id}` (outline) | 15.4 ms | 20.9 ms | 23.3 | 7.3 |
| `GET /api/learning-sessions/{id}/contents` | 14.6 ms | 34.8 ms | 22.9 | 13.25 |
| `GET /api/me/enrollments` | 8.2 ms | 11.9 ms | 23.8 | 1.5 |

\* `queries_per_request` của harness đếm cả `BEGIN`/`ROLLBACK` và query poll của worker chạy nền. Trừ phần đó, `outline` thực tế ~2,0 query/request; `session_contents` ~8,0; `replay` ~10,0; **`aoi_summary` chỉ ~3 query/request**. Vì vậy `aoi_summary` không phải N+1 — nó là một query khổng lồ + xử lý CPU.

### Bằng chứng đo trực tiếp (stack dev, 11.201 content views / 100 học viên / 2.074 visit)

| Phép đo | Kết quả |
|---|---|
| `POST aoi-summary` (includeShort, surface=all) | **1,40 s**, response **875 KB** |
| ORM fetch đúng query của service (11.201 row × 8 entity) | **0,94–1,05 s** |
| Raw asyncpg cùng bộ cột đầy đủ | **542 ms** |
| Raw asyncpg chỉ cột cần (slim) | **73 ms** (nhanh hơn 7,4×) |
| Tổng `pg_column_size` của payload | **~68 MB**; riêng `slides` **50,5 MB** (`embedding` 1024 chiều + `transcript` + `content_tsv`) |
| Vòng lặp aggregate Python (sau khi fetch) | **~0,44 s** |
| `model_dump` + `json.dumps` | ~7 ms (serialize **không** phải nút thắt) |
| k6 aoi_summary 2 VU | 1,379 rps ≈ **2 request đồng thời × 1,45 s** → công suất 2 worker bị chiếm trọn |
| Export visit (29.377 sample) | đọc + top-N sort toàn bộ 29.377 row cho 1.000 row trả về, 22 ms/page đầu |
| Chatbot (baseline) | TTFT p95 **34,7 s**, total p95 **63,6 s** |
| Gaze WS 8 phiên | 107,9 resp/s, **drop 10,1%**, p95 **145 ms** |

## 1. Bảng điểm nghẽn

| Impact | File:Dòng | Luồng bị ảnh hưởng | Nguyên nhân gốc rễ | Hướng tối ưu đề xuất (1 dòng) |
|---|---|---|---|---|
| **High** | `backend/app/services/analytics/summary.py:132` | `POST /teacher/courses/{id}/analytics/aoi-summary` | `select(ContentView, LearningSession, Lesson, Slide, Enrollment, User, StudentProfile, CourseVisit)` nạp full entity: `slides.embedding` 1024 chiều + `transcript` + `content_tsv`, `content_views.heatmap_grid` (24×24 JSONB, không dùng), `users.password_hash`; 11.201 view → ~68 MB payload, ORM fetch ~0,95 s (raw cùng cột 542 ms, slim 73 ms) | Chỉ select cột cần (id/title/position/page_number/aoi_stats/…), bỏ `Slide.embedding`/`transcript`/`content_tsv`, `heatmap_grid` và `User.password_hash`; dùng `load_only` hoặc raw SQL. |
| **High** | `backend/app/services/analytics/summary.py:228` | aoi-summary (toàn bộ dashboard Trực quan hoá) | Không bound thời gian/pagination: mọi content view của khóa từ trước tới nay vào RAM; vòng lặp `262-406` nhân 4 bucket × từng AOI × 11k row (~0,44 s CPU), chặn event loop | Bắt buộc `from`/`to` + limit/keyset; đẩy aggregate `aoi_stats` xuống SQL (`jsonb_each`) hoặc rollup table theo visit/slide. |
| **High** | `backend/Dockerfile:54`, `docker-compose.yml:253` | Toàn bộ API | `WEB_CONCURRENCY=2` trên 4 CPU; request analytics 1,4 s chủ yếu CPU-bound (ORM hydrate + Python) nên chiếm trọn event loop của worker; 2 VU đạt đúng 1,38 rps | Tăng worker lên 4 + giảm pool/worker; trước mắt đẩy việc nặng sang SQL/background và cache kết quả. |
| **High** | `backend/app/api/routes/gaze_ingest.py:470` | `POST /api/learning-sessions/{id}/gaze-batches` | Mỗi batch 1,5 s đều `UPDATE content_views SET analysis_status='pending'` kể cả khi `stored=0` hoặc đã pending; 1 học viên ≈ 40 UPDATE/phút/view → dead tuple, WAL, bloat | Chỉ UPDATE khi `analysis_status <> 'pending'` (`WHERE` điều kiện) hoặc đánh dấu một lần khi đóng view/session. |
| **High** | `backend/app/services/metrics.py:163`, `:255` | Worker `analyze_lesson` | `select(GazeSample)` toàn bộ sample vào ORM rồi sửa từng row (`slide_x/y`, `aoi_label`, `quality_flags`) và flush trong 1 transaction; view 1 giờ @15 FPS = 54k row → 54k UPDATE, transaction dài, RAM lớn | Chunk theo 2–5k row + `UPDATE … FROM (VALUES …)`; tính metrics bằng SQL; commit theo lô. |
| **High** | `backend/app/services/analysis/export.py:13` + `:219` + `:325` | `GET /teacher/visits/{id}/export`, `/teacher/lessons/{id}/export` | Keyset `(event_time, id)` nhưng filter theo visit/lesson → mỗi page scan + `top-N sort` toàn bộ sample của visit (EXPLAIN: đọc/sort 29.377 row cho 1.000 row); page sau lặp lại → O(n²/page) | `ORDER BY (content_view_id, event_time, id)` dùng `idx_gaze_samples_view_time`, hoặc thêm `visit_id`/`lesson_id` vào `gaze_samples` + index. |
| **High** | `backend/app/api/routes/analytics.py:394` + `:411` + `backend/app/services/analysis/export.py:272` | Export streaming | Route giữ `db` dependency (đã BEGIN) suốt thời gian stream; generator mở session riêng nhưng không commit giữa các page → connection `idle in transaction`, `idle_in_transaction_session_timeout=30s` có thể kill; vài export đồng thời làm cạn pool 10 | `await db.close()` trước khi trả `StreamingResponse` (như `chat.py:197`); commit/close từng page; engine/DSN riêng cho export. |
| **High** | `backend/app/maintenance.py:145` + `:169` | Maintenance retention gaze | `DELETE FROM gaze_samples WHERE event_time < cutoff` không LIMIT, chạy chung transaction với 4 tác vụ khác; ngày cutoff xoá hàng triệu row → lock/WAL/bloat, ảnh hưởng trực tiếp insert gaze | Batch `LIMIT 10k` + commit từng batch, chạy off-peak; cân nhắc partition theo tháng. |
| **High** | `backend/app/services/course_stats.py:20` + `backend/app/services/content/courses.py:77` | `GET /teacher/courses` | Query attention join lessons→sessions→content_views của mọi khóa, không giới hạn thời gian, chạy lại mỗi lần mở trang; baseline **22 ms/call DB** và tăng tuyến tính theo lịch sử; 3 aggregate tuần tự | Rollup `course_stats` bằng job/trigger hoặc cache Redis 30–60 s; gộp 3 aggregate vào 1 query. |
| **Med** | `backend/app/services/content/slide_reads.py:27` + `backend/app/services/analytics/replay.py:145` | `/api/lessons/{id}/contents`, `/api/learning-sessions/{id}/contents`, replay | `select(Slide)` kéo `embedding` + `transcript` + `content_tsv` dù DTO chỉ cần id/title/page_number; 1 lesson 50 slide ≈ 250 KB vô ích | `load_only`/select cột DTO; tách model `SlideSummary` cho read path. |
| **Med** | `backend/app/api/routes/learning_sessions.py:253` + `backend/app/services/content/slide_reads.py:68` | `GET /api/learning-sessions/{id}/contents` | Resolve lesson→module→course 2 lần (route và `course_of_lesson` trong service), cộng media asset → ~8 query thật/request | Truyền `lesson`/`course` đã có vào service, bỏ lần resolve thứ 2; join media asset một lần. |
| **Med** | `backend/app/api/routes/analytics.py:98` | `GET /teacher/courses/{id}/visits` | 2 aggregate riêng (session count + metrics) cùng quét `learning_sessions`/`content_views` cho 200 visit; biểu thức dwell lặp lại | Một query CTE trả count + sums; hoặc rollup theo visit. |
| **Med** | `backend/app/services/analytics/replay.py:190` | `GET /teacher/visits/{id}/replay` | ~10 round trip tuần tự + `_slide_aois_out`/`_stats_out` dựng lại Pydantic cho từng view; `sample_stats` (`:240`) scan toàn bộ sample của visit | Gộp participant+visit+course; cache AOI theo `slide_id`; lưu first/last/count trong `content_views` thay vì aggregate lại. |
| **Med** | `backend/app/services/analytics/summary.py:180` + `:531` | `POST …/analytics/heatmap` | `EXISTS` tương quan cho từng content view + select full entity; mỗi view một subplan | Thêm cột `has_samples`/`sample_count` hoặc `LEFT JOIN LATERAL` một lần; select cột cần. |
| **Med** | `backend/app/services/analytics/summary.py:204` | aoi-summary + replay | `_slide_names` nạp toàn bộ `aois` của mọi slide trong khóa mỗi request (4.800 row trong baseline) | Cache map label→name theo slide/course 60 s (Redis hoặc in-process). |
| **Med** | `backend/app/crud/user.py:80` | Mọi request đã đăng nhập | Luôn `GET auth:user:*` Redis trước khi xét memory cache → thêm 1 RTT/request dù memory đã có; TTL 30 s | Đảo thứ tự memory → Redis; cache theo request context. |
| **Med** | `backend/app/api/routes/courses.py:363` | `GET /api/courses/{id}` (outline) | Check course + enrollment + `can_access_course` trước khi đọc Redis cache outline → cache hit vẫn tốn 2–3 query | Cache quyết định access/enrollment 30 s, hoặc đọc cache trước rồi fallback check khi miss. |
| **Med** | `backend/app/api/routes/courses.py:43` + `:327` | PATCH require-calibration / add students | `_invalidate_enrollment_cache` DEL từng student tuần tự; lớp 200 SV = 200 RTT Redis trong một request | `UNLINK` theo pipeline/batch hoặc bump version key của course. |
| **Med** | `backend/app/services/analysis/__init__.py:212` | Lưu UI AOI | `UPDATE content_views SET analysis_status='pending'` toàn bảng + `EXISTS` tương quan; global write lock/bloat | Chỉ update view thuộc lesson bị ảnh hưởng; batch theo `IN (view_ids)`. |
| **Med** | `backend/app/api/routes/gaze_ingest.py:397` + `:461` | Gaze batch | 4 round trip DB (session join, content view, layout, insert) + 3 Redis (auth GET, INCR, EXPIRE) mỗi 1,5 s/học viên; `RETURNING id` cho mọi row | Cache mapping presentation→session/layout TTL ngắn; dùng rowcount thay RETURNING; gộp validate vào `INSERT … SELECT`. |
| **Med** | `db/migrations/001_baseline.sql:487` + `backend/app/api/routes/gaze_ingest.py:461` | Ghi `gaze_samples` | Mỗi sample cập nhật pkey + unique `(view, batch, sequence)` + `idx_gaze_samples_view_time` + `idx_gaze_samples_event_time` (+ `aoi_label`) + FK check; 15 sample/s/học viên → write amplification | Thay `idx_gaze_samples_event_time` bằng BRIN (append-only, retention); đổi `idx_gaze_samples_aoi_label` thành `(content_view_id, aoi_label)`; hoặc `COPY` theo batch. |
| **Med** | `backend/app/api/routes/analytics.py:212` | `GET /teacher/visits/{id}/gaze` | OFFSET pagination trên `gaze_samples` (limit 1000) → deep offset scan + discard | Keyset `(event_time, id)` như `/samples` và `/replay`. |
| **Med** | `backend/app/services/course_students.py:116` | `GET /teacher/courses/{id}/students` | Dựng toàn bộ ma trận student×lesson (100×105 = 10.500 Pydantic) không phân trang; response 442 KB ở 100×50 | Trả summary + `lessons` lazy/paginate; hoặc chỉ lesson có dữ liệu. |
| **Med** | `backend/app/core/config.py:41`–`:43` + `backend/app/db/session.py:16` | Toàn bộ DB | `DB_PREPARED_STATEMENT_CACHE_SIZE=0` mặc định dù stack local/prod nối trực tiếp Postgres → parse/plan lại mọi query | Đặt >0 khi không dùng PgBouncer transaction mode; giữ 0 chỉ cho profile `pgbouncer`. |
| **Med** | `backend/app/db/session.py:21` | Export + analytics khi dữ liệu lớn | `statement_timeout=15s` áp cho mọi statement của engine API, gồm export page và analytics | Engine riêng cho export/worker với timeout dài hơn, hoặc `SET LOCAL statement_timeout` theo session. |
| **Med** | `nginx/nginx.conf:48` + `nginx/default.conf:158` | Toàn bộ API sau nginx | `api_rl 20 r/s` và `perip_api 50` theo IP; một lớp học sau NAT trường = 1 IP → 30 SV × 1 batch/1,5 s ≈ 20 r/s chạm trần | Nâng rate/zone riêng cho `/api/learning-sessions/*/gaze-batches`, hoặc key theo user/session thay vì IP. |
| **Med** | `services/chatbot/app/workflow/pipeline.py:105` | `POST /chat/stream` → backend `/api/courses/{id}/chat/stream` | Citation gate buffer cả câu trả lời đến khi thấy citation hoặc 200 từ mới nhả token; fail thì chạy lại generation (`citation_retry_max=1`) → TTFT p95 34,7 s / total 63,6 s | Gate trên marker citation thay vì buffer cả câu; phát status/token sớm; hạ retry hoặc kiểm citation hậu kiểm. |
| **Med** | `services/chatbot/app/workflow/embedding_queue.py:61` + `:139` | Ingest slide + chat query | Một thread embedding cho cả ingest và query; ingest batch 8 × ~8 s = 64 s/lần, query phải chờ hết batch hiện tại | Tăng worker embedding/GPU, batch lớn hơn, hoặc tách pool query khỏi ingest. |
| **Med** | `backend/app/services/chat_transport.py:56` | SSE chat | Cứ 5 s không có line → `ensure_access()` mở `SessionLocal` mới và chạy lại 3–4 query; TTFT 30 s ≈ 6 lần check | Cache kết quả access 30 s trong stream; chỉ check lại khi có event hoặc dùng `revoked_at`. |
| **Med** | `services/gaze/app/services/runtime.py:205` | WS `/session/{sid}/stream` | 1 CPU thread + 1 GPU thread, queue 8/1, không batch cross-session; 8 phiên 15 FPS = 120 fps > ~90 fps capacity → drop 10%, p95 145 ms | Batch frame nhiều session trên GPU, tăng replica + affinity, hoặc hạ FPS động theo `suggestedFps` (đã có). |
| **Med** | `services/chatbot/app/workflow/retrieval.py:50` | Retrieval dense | `1 - (embedding <=> $1) >= threshold` + ORDER BY trên view join 5 bảng → planner không dùng `idx_slides_hnsw` (EXPLAIN 09: nested loop + sort 120 row) | Query thẳng `slides` với subquery course, bỏ threshold khỏi WHERE, `ORDER BY <=> LIMIT n`; partial index theo course nếu cần. |

**Đọc bảng này theo thứ tự:** 3 dòng High đầu tiên giải thích gần như toàn bộ khoảng cách giữa baseline (aoi_summary 1,25 s) và mục tiêu < 200 ms. Các dòng `High` còn lại là write amplification và I/O của worker/export; các dòng `Med` chủ yếu là round-trip thừa và cache đặt sai chỗ.

## 2. Cần đo thêm runtime

1. **Planner ở quy mô 10× (aoi_summary / course_stats / course_visits).** Code tĩnh không kết luận được vì planner đã đổi kế hoạch theo kích thước: dev 11k row chọn `Seq Scan` + Hash Join trên `content_views`, còn benchmark 19k row chọn nested loop + `idx_content_views_session` 580 lần. Cần `EXPLAIN (ANALYZE, BUFFERS)` trên bản sao ≥100k content_views và ≥50M gaze_samples để xác định: (a) có cần composite `(session_id, analysis_version, surface)` hoặc partial index `WHERE analysis_status='ready'` không, (b) có nên thêm `enrollment_id`/`course_id` denormalized vào `content_views` cho filter dashboard không, (c) query có vượt `statement_timeout=15s` không.
2. **Contention pool + streaming.** Chạy 5–10 export/replay đồng thời, đo `pg_stat_activity` (`state`, `wait_event`, `xact_start`) và thời gian chờ pool: xác nhận request-scoped session bị `idle in transaction` trong lúc stream, `idle_in_transaction_session_timeout=30s` có kill connection không, và đo thời gian từng page export trên visit ≥100k sample để xác nhận hành vi O(n²/page).
3. **Worker analysis + gaze write amplification.** Profile `analyze_content_view` trên một view 30–60 phút (27k–54k sample): tách thời gian `select` / ORM mutate / flush, đếm số UPDATE, WAL bytes và lock wait; đồng thời đo `n_tup_upd` + dead tuple của `content_views` khi 100 học viên gửi batch 1,5 s để định lượng đóng góp của `analysis_status='pending'` và quyết định có cần partition/autovacuum tuning.

## 3. Ghi chú phạm vi

- Phần này chỉ kết luận cho backend + DB + phần giao tiếp phía backend. Chi tiết nội bộ chatbot (retrieval, prompt, LLM queue) và gaze (MediaPipe/UniGaze, smoothing, calibration) để Phần 2.
- Không có thay đổi code nào được thực hiện. Các phép đo local dùng read-only query và một request `aoi-summary`; chỉ có thao tác đăng nhập admin để lấy token (có thể cập nhật `last_login_at`).

---

# Perf audit — Phần 2: 2 AI services (gaze + chatbot)

> Phạm vi: `services/gaze` (WS frame → decode → MediaPipe → UniGaze → calibration → response) và `services/chatbot` (ingest slide + query RAG), gồm cả tài nguyên cấp cho 2 service trong `docker-compose.yml`.
> Nguồn: code hiện tại; `benchmarks/baseline/20261120T180000Z-baseline/` (`gaze/stage-latency.json`, `gaze/ws-load.json`, `chatbot/components*.json`, `chatbot/query-chatbot.json`, `chatbot/ingest.json`); `EXPLAIN` + catalog read-only trên stack dev (pgvector 0.8.7, 513 slide); `docker stats`.
> Không sửa code. Dataset local nhỏ hơn production; số đo chỉ dùng để xác định bậc độ lớn và thứ tự ưu tiên.

## 0. Vòng đời đã trace

**Luồng A — eye-tracking real-time**

```text
Browser: canvas 480px JPEG q=0.78 (toBlob trên main thread)
  → WS binary [4B header len][JSON header][JPEG]; throttle 56 ms (GAZE_FPS=15)
  → mailbox 1 slot (drop "superseded") → process_loop (drop nếu > 200 ms)
  → CPU thread: cv2.imdecode → cvtColor BGR→RGB → MediaPipe FaceDetector (BlazeFace, IMAGE mode)
                → crop → solvePnP ×2 → warpPerspective 224×224
  → GPU thread: uint8 H2D → /255 + normalize → ViT-B/16 → pred[0].tolist() (D2H + sync)
                → calibration lstsq → One-Euro → JSON response
```

Hàng đợi: mailbox 1, CPU queue 8, GPU queue 1; 1 thread CPU + 1 thread GPU mỗi replica. Không có torch/cv2 trên event loop.

**Luồng B — RAG ingest**

```text
POST /teacher/lessons/{id}/slides/upload        (giữ tới 50 MB trong RAM)
  → content-worker: 1 asyncio task, poll 3 s, limit 1
      → LibreOffice headless → PDF → N slide "pending" → enqueue index_slides
  → embedding-worker: 1 asyncio task, poll 5 s, limit 1
      → POST /ingest/slides (batch ≤ 4 slide)
          → chatbot: _job_lock → ThreadPool(4), mỗi slide:
              pymupdf.open(stream=pdf) → render 150 DPI PNG → base64
              → VLM 1 ảnh/request (semaphore 1-2, nhường chat)
              → _embed_lock → embed_documents([1 transcript])
              → 2-3 UPDATE slides (FTS generated + GIN + HNSW)
```

**Luồng C — RAG retrieval**

```text
fetch SSE → nginx (proxy_buffering off) → backend route (access + context + commit message)
  → chatbot /chat/stream (20 slot) → lms.check_access (HTTP backend)
  → rewrite/HyDE (LLM structured, tuỳ câu) → query embedding (1 thread CPU dùng chung ingest)
  → song song: FTS + dense + dense-HyDE trên view 5 join → RRF top-8
  → event citations → stream answer + citation gate (buffer 200 từ, retry tối đa 1)
```

**Số đo baseline dùng trong bảng**

| Luồng | Phép đo | Giá trị |
|---|---|---:|
| A | stage p50: decode / detect / warp / forward / tổng | 0,52 / 1,42 / 0,64 / **8,17** / **10,96 ms** |
| A | 8 phiên WS đồng thời | 107,9 resp/s, **drop 10,1%**, p95 **145 ms** |
| B | ingest 2 slide (wall **25,44 s**) | render 58 ms, VLM **10,74 s**, embedding **8,16 s**, DB 17+9 ms |
| C | retrieval cold / warm | **1.316 ms** / 10,7 ms |
| C | chat end-to-end | TTFT p95 **34,7 s**, total p95 **63,6 s** |
| — | VRAM gaze fp32 / RSS gaze / RSS chatbot | 346 MiB alloc, 388 MiB reserved / 1,15 GiB / 1,53 GiB |

**Đã kiểm tra và không phải nút thắt:** model load 1 lần lúc startup (không load theo request/frame); gaze dùng `.eval()` + `torch.inference_mode()`; chatbot warm embedding trong lifespan; calibration nằm trong RAM theo session, không đọc DB mỗi frame; deque/queue/session của gaze đều bounded (không rò rỉ bộ nhớ). Vấn đề của 2 service là **tuần tự hoá, batch = 1, tài nguyên cấp thiếu và query shape**, không phải load model lặp lại.

## 1. Bảng điểm nghẽn

### Luồng A — Eye-tracking real-time

| Impact | File:Dòng | Bước bị nghẽn | Nguyên nhân gốc rễ | Hướng tối ưu đề xuất |
|---|---|---|---|---|
| **High** | `services/gaze/app/services/runtime.py:205-207`, `:370-372` | Ghép CPU → GPU | GPU queue chỉ 1 slot; CPU thread block `put(timeout=200 ms)` nên không chuẩn bị trước frame kế; 1 CPU + 1 GPU tuần tự; 8 phiên = 120 fps vượt ~90 fps fp32 → drop 10,1%, p95 145 ms | Cho GPU queue sâu 2-4 và batch nhiều session mỗi forward (tăng replica chỉ lợi khi mỗi replica có GPU riêng). |
| **High** | `services/gaze/app/services/pipeline.py:178`, `:188` | Forward UniGaze | Batch cố định 1; `pred[0].tolist()` ép D2H + synchronize mỗi frame; forward 8,17 ms = 75% ngân sách 10,96 ms nên GPU idle giữa các frame | Gom N frame khác session vào 1 batch và copy output 1 lần (`pred.to("cpu", non_blocking=True)` với pinned buffer). |
| **High** | `docker-compose.yml:539` | Chọn precision | `INFERENCE_PRECISION` mặc định **fp32**; README cùng RTX 3060 ghi fp16 ~7-8 ms và ~235 fps so với ~115 fps fp32 | Bật fp16 sau A/B accuracy (§2), giữ fp32 làm fallback theo từng model. |
| **High** | `docker-compose.yml:516-517`, `:554` | Co-locate 2 replica trên 1 GPU | Mỗi replica load model + CUDA context riêng (346 MiB alloc / 388 MiB reserved fp32), cùng tranh SM; không có batch xuyên session trong 1 process | Dùng 1 replica + batch nội bộ (hoặc MPS/time-slicing có đo), thay vì scale replica trên cùng card. |
| **Med** | `services/gaze/app/services/pipeline.py:175-181` | Chuẩn bị tensor | `.permute` tạo view non-contiguous rồi `.to(device)` synchronous trên pageable memory; normalize float32 trên GPU tạo 2 temporary | `.contiguous()` trước H2D, `pin_memory` + `non_blocking=True`, fuse `/255` vào mean/std. |
| **Med** | `services/gaze/app/services/pipeline.py:33`, `:68`, `:102` | Decode / đổi màu | Mỗi frame: `imdecode` ra BGR → `cvtColor` ra RGB → `mp.Image` copy thêm lần nữa; client còn JPEG-encode trên main thread | Gửi ảnh 320px hoặc dùng WebCodecs/OffscreenCanvas; tránh copy RGB thứ ba nếu MediaPipe nhận đúng buffer. |
| **Med** | `services/gaze/app/services/pipeline.py:61`, `:69` | Detect mỗi frame | `RunningMode.IMAGE` chạy full BlazeFace graph mỗi frame dù mặt gần như đứng yên (1,42 ms/frame) | Dùng `RunningMode.VIDEO` + timestamp, chỉ re-detect mỗi N frame hoặc khi IoU tụt, giữ detect toàn frame làm fallback. |
| **Med** | `services/gaze/app/services/preprocessing.py:43`, `:62`, `:101-104`, `:119` | Warp / solvePnP | `Rodrigues` tính 2 lần; camera matrix + `zeros((1,5))` + `np.linalg.inv(cam)` dựng lại mỗi frame; warp 0,64 ms | Cache camera + inverse theo `(w,h)` và truyền lại `h_r` đã tính cho `normalize_image`. |
| **Med** | `services/gaze/app/services/runtime.py:309-314` | Timeout | `wait_for(5 s)` không huỷ job đã vào queue; job vẫn chạy GPU rồi bỏ kết quả → đốt inference đúng lúc quá tải | Gắn cờ cancel vào `FrameJob`, worker bỏ qua job đã timeout trước khi forward. |
| **Med** | `services/gaze/app/services/runtime.py:101-124`, `:167-179` | Thống kê | Lock toàn cục 3-4 lần/frame; `suggested_fps()` scan 512 entry dưới lock đúng lúc overload | Cập nhật `suggestedFps` bằng EMA 1 s/lần; counter theo session không lock. |
| **Med** | `services/gaze/app/api/session.py:263` | Gửi kết quả | `await ws.send_json` nằm trong process loop; client chậm chặn pipeline của session đó (mailbox 1 slot nên frame bị bỏ) | Tách sender task + queue riêng, hoặc `send_bytes` với payload đã serialize. |
| **Med** | `services/gaze/app/api/session.py:233-236` | Throttle | `last_frame_at` cập nhật trước khi parse/validate; frame hỏng vẫn "ăn" cửa sổ 56 ms nên frame hợp lệ kế bị drop oan | Chỉ cập nhật `last_frame_at` sau khi parse + kiểm size thành công. |
| **Med** | `services/gaze/app/services/sessions.py:78-84`, `services/gaze/app/main.py:46-50` | Vòng đời session | `last_active` chỉ cập nhật ở HTTP `get`, không cập nhật khi stream frame; bài giảng > 30 phút bị cleanup xoá session giữa phiên → mất calibration | Touch session trong `process_loop` hoặc gia hạn TTL khi WS còn mở. |
| **Med** | `frontend/hooks/use-gaze-tracker.ts:201-216` | Capture phía client | `drawImage` + `toBlob` JPEG q=0.78 trên main thread mỗi 56 ms; encode/decode JPEG vừa tốn CPU client vừa mất chi tiết | Chuyển sang `OffscreenCanvas` trong worker hoặc WebCodecs; giữ ngưỡng `bufferedAmount` hiện có. |
| **Low** | `services/gaze/app/protocol.py:22` | Parse frame | `data[4+header_len:]` copy toàn bộ JPEG (tới 1 MiB) mỗi frame | Truyền `memoryview` + offset thẳng vào `cv2.imdecode`. |

### Luồng B — RAG ingest

| Impact | File:Dòng | Bước bị nghẽn | Nguyên nhân gốc rễ | Hướng tối ưu đề xuất |
|---|---|---|---|---|
| **High** | `services/chatbot/app/services/ingest.py:94`, `:262-268` | Embedding từng slide | `_embed_lock` + `embed_documents([transcript])` → batch thực tế = 1; baseline 8,16 s/slide, chiếm 64% wall 2 slide; `batch_size=8` và coalescing 10 ms bị vô hiệu cho ingest | Bỏ lock, gom transcript nhiều slide thành batch ≥ 8, giữ nguyên `max_length` và `normalize_embeddings`. |
| **High** | `docker-compose.yml:404-405` | Tài nguyên embedding | embedding-worker chỉ `cpus: 1.0`; Qwen3-Embedding-0.6B chạy CPU 1 core; 100 slide ≈ 13,6 phút chỉ riêng embedding | Nâng 4 core (hoặc GPU riêng) và set `torch.set_num_threads` khớp quota. |
| **High** | `services/chatbot/app/services/ingest.py:62`, `:283-284`, `services/chatbot/app/workflow/workload.py:10` | VLM per-slide | ThreadPool 4 nhưng `VLM_INGEST_CONCURRENCY=1` (code) / 2 (compose) → batch 4 chạy 2-4 wave; mỗi ảnh 1 request, 10,74 s/slide | Đặt concurrency bằng số thread, hoặc batch nhiều ảnh/1 request nếu VLM hỗ trợ, vẫn giữ gate nhường chat. |
| **High** | `services/chatbot/app/api/ingest.py:26`, `:45-51` | Tuần tự hoá ingest | `_job_lock` toàn cục: mọi `POST /ingest/slides` xếp hàng trong 1 process, không ingest song song 2 khóa | Bỏ lock toàn cục, chỉ giới hạn theo `(lesson, batch)` hoặc semaphore theo capacity VLM. |
| **High** | `services/chatbot/app/services/ingest.py:191-202` | Render slide | `pymupdf.open(stream=pdf)` mở/parse lại toàn bộ PDF cho **từng** slide → O(n²); PNG lossless 150 DPI base64, không resize/JPEG | Mở PDF 1 lần/lesson (cache `Document`) và render JPEG q85 hoặc DPI thấp hơn sau khi đo accuracy. |
| **High** | `backend/app/worker_loop.py:32-42` | Nhịp worker | Sleep 3 s (content) / 5 s (embedding) sau **mọi** vòng, kể cả vừa xử lý xong job → cộng dead time mỗi job; chỉ 1 job/lần | Sleep ngắn 0,2-0,5 s khi vừa có việc, sleep dài chỉ khi idle. |
| **Med** | `backend/app/embedding_worker.py:20-26`, `backend/app/services/embedding_jobs.py:144-156` | Throughput hàng đợi | `limit=1`, 1 container, claim tuần tự → toàn hệ chỉ 1 lesson ingest tại một thời điểm | Claim `LIMIT N` rồi `asyncio.gather` N job, với N theo capacity CPU/VLM. |
| **Med** | `services/chatbot/app/services/ingest.py:107-108`, `:224-259` | Ghi DB | Mỗi slide 2-3 lần checkout + UPDATE riêng; mỗi UPDATE tính lại `to_tsvector(transcript)` (generated) + GIN + chèn HNSW | Gom UPDATE theo batch (`executemany` / `UPDATE … FROM VALUES`) và chỉ set `pending` 1 lần/batch. |
| **Med** | `services/chatbot/app/services/ingest.py:177-189` | Cache PDF | `storage.load` nằm ngoài `_pdf_lock` → 4 thread cùng đọc/tải 1 PDF 50-100 MB khi cold cache; cache chỉ 3 PDF | Single-flight theo key (lock/future per-key) và tăng cache theo lesson đang ingest. |
| **Med** | `backend/app/api/routes/lessons.py:98-108`, `backend/app/services/content/slides.py:101-102`, `:214-217` | Upload | File 50 MB buffer 2 lần trong RAM (`bytearray` + `bytes`) và validate PDF 2 lần (API + worker) | Đọc/ghi streaming ra staging và validate 1 lần trong worker. |
| **Med** | `backend/app/api/routes/courses.py:215-219`, `backend/app/services/embedding.py:252-262` | Publish 409 | Chỉ 1 slide chưa ready → mark pending + force reindex **toàn khóa** | Chỉ enqueue slide/lesson còn thiếu và giữ `only_pending`. |
| **Med** | `backend/app/services/content/slides.py:244-259` | Re-upload | Upload lại PDF giống hệt vẫn xoá hết slide và chạy lại VLM từng trang (hash chỉ dedupe `media_assets`) | So hash PDF đã lưu; nếu giống thì giữ slide + index, chỉ cập nhật metadata. |
| **Med** | `services/chatbot/app/workflow/providers.py:75-82`, `services/chatbot/app/services/ingest.py:91` | Nhân đôi model embedding | `get_embedding()` và `get_embedding("local")` là 2 `lru_cache` key khác nhau → 2 model + 2 worker thread; RSS 1,53 GiB trên trần 4 GiB; instance thứ 2 load lúc ingest và không được close | Dùng 1 key duy nhất (gọi không tham số ở cả hai chỗ) hoặc cache theo `model_path`. |
| **Med** | `services/chatbot/app/services/ingest.py:88-90`, `services/chatbot/app/workflow/providers.py:42` | Sinh transcript | `with_structured_output(function_calling)` + `VLM_MAX_TOKENS=8192`, không streaming → decode dài, tốn token cho wrapper JSON | Giới hạn `max_tokens` theo độ dài slide và dùng JSON mode/plain text nếu server hỗ trợ. |
| **Med** | `backend/app/services/embedding.py:207-216` | Gọi chatbot | Batch 4 dù request cho phép 2000; timeout 900 s cho cả POST; response bị bỏ qua nên slide fail vẫn mark job `ready` | Tăng batch 16-32 và đọc `failed` để retry đúng slide lỗi. |
| **Med** | `services/chatbot/app/services/ingest.py` (không có timing) | Observability | Không log thời gian render/VLM/embed/DB theo slide → không quy được trần 25 s | Thêm 4 mốc `perf_counter` mỗi slide vào log hoặc metrics. |

### Luồng C — RAG retrieval

| Impact | File:Dòng | Bước bị nghẽn | Nguyên nhân gốc rễ | Hướng tối ưu đề xuất |
|---|---|---|---|---|
| **High** | `services/chatbot/app/workflow/retrieval.py:50-59`, `db/migrations/001_baseline.sql:251-253`, `:618-625` | Dense search | `course_id` nằm sau 5 join của view, `ORDER BY embedding <=> …` trên bảng đã join + threshold trong WHERE → planner không dùng HNSW (`idx_slides_hnsw.idx_scan=0`, EXPLAIN: nested loop + sort) | Query thẳng `slides` với `lesson_id IN (subquery)`, bỏ threshold khỏi WHERE rồi lọc sau `LIMIT`, hoặc denormalize `course_id` + partial HNSW. |
| **High** | `services/chatbot/app/workflow/pipeline.py:105-152` | TTFT / citation gate | Buffer 200 từ trước token đầu; chưa thấy `[n]` thì **huỷ stream và sinh lại** (tối đa 2 lần) → TTFT p95 34,7 s, total 63,6 s | Gate trên marker citation thay vì buffer cả câu; phát token ngay, kiểm citation hậu kiểm và bỏ retry toàn bộ. |
| **High** | `services/chatbot/app/workflow/embedding_queue.py:37`, `:61-98` | Embedding query | 1 thread/model dùng chung query + ingest; ingest batch 8 × ~8 s ≈ 64 s → query xếp sau, timeout 60 s → lỗi chat khi đang index | Pool riêng cho query (model/thread riêng hoặc ưu tiên tuyệt đối + batch nhỏ). |
| **High** | `services/chatbot/app/workflow/providers.py:75-82`, `services/chatbot/app/workflow/retrieval.py:84`, `services/chatbot/app/services/ingest.py:91` | Bộ nhớ | 2 instance model embedding (~1,2 GB weights mỗi bản + 2 worker thread) trong 1 process, trần 4 GiB | Hợp nhất key cache để ingest và query dùng chung 1 model. |
| **High** | `services/chatbot/app/workflow/query.py:59-71`, `:82-104` | Trước retrieval | Rewrite/HyDE là 1 LLM call structured trước khi search; HyDE sinh tới 4000 ký tự + embedding thứ 2 → cộng thẳng vào TTFT | Cache rewrite/HyDE theo `(câu hỏi, hash history)`; chỉ HyDE khi thật mơ hồ; timeout 2-3 s + fallback. |
| **Med** | `services/chatbot/app/workflow/retrieval.py:21-36`, `:93-111` | Payload candidate | 3 nhánh × 20 candidate, mỗi row kéo full `transcript` + metadata không dùng; chỉ 8 row cuối được dùng | Vòng 1 chỉ select `id/score/lesson`, vòng 2 fetch transcript cho top-8. |
| **Med** | `services/chatbot/app/workflow/retrieval.py:206-215`, `services/chatbot/app/workflow/generation.py:56-59` | Prompt | Ghép full transcript 8 slide + assignment 30k ký tự + history 16k + LMS text, không có token budget | Đặt budget 6-8k token, truncate theo đoạn khớp query, dedupe theo slide. |
| **Med** | `services/chatbot/app/workflow/retrieval.py:93-111`, `services/chatbot/app/db.py:36-65` | Pool DB | Mỗi request mở 2-3 connection (FTS + dense + HyDE) trong khi pool max 10 và cho 20 chat slot → checkout chờ/timeout 10 s | Một connection/request hoặc gộp 3 nhánh vào 1 round trip; tăng pool hoặc giảm max concurrent. |
| **Med** | `services/chatbot/app/workflow/pipeline.py:157`, `services/chatbot/app/workflow/lms.py:53-54` | Trước retrieval | Mỗi message (kể cả "xin chào") gọi HTTP backend `/internal/chat/lms-query` để check access, dù backend vừa check ở route | Bỏ `check_access` khi backend đã xác thực, hoặc cache 30-60 s theo session. |
| **Med** | `.env:94-96` (không có code) | Cache | `RAG_RETRIEVAL_CACHE_*` chỉ tồn tại trong `.env`, không code/compose nào đọc; chỉ có cache embedding query (LRU 1024, 900 s) | Implement cache retrieval/answer TTL ngắn, key gồm course + query chuẩn hoá + pipeline/model version. |
| **Med** | `services/chatbot/app/workflow/retrieval.py:113-137` | Song song hoá | BM25 không chạy cho tới khi cả query + HyDE embed xong, dù BM25 không cần vector | Khởi động BM25 song song với embedding (gather cả 3 nhánh). |
| **Med** | `services/chatbot/app/workflow/retrieval.py:55-58` | Recall ANN | Không set `hnsw.ef_search` (mặc định 40) và `iterative_scan=off`; nếu chuyển sang HNSW, post-filter course có thể trả thiếu `LIMIT` | Set `ef_search ≥ 4×top_k` và `iterative_scan=relaxed_order`, đo recall@8 trước khi đổi. |
| **Med** | `services/chatbot/app/api/chat.py:27-31`, `services/chatbot/app/workflow/llm.py:54-98` | Capacity | 20 chat slot nhưng chỉ 4 generation slot + queue timeout 30 s → request giữ slot chờ; baseline 5 VU đã 12,5% lỗi | Cân slot theo capacity provider; trả 429 sớm thay vì giữ slot, backpressure theo độ dài hàng đợi. |
| **Low** | `backend/app/services/chat_transport.py:90`, `backend/app/services/study_chat.py:197` | SSE | Mỗi token bị `json.loads` rồi `json.dumps` lại ở backend rồi `JSON.parse` ở frontend | Proxy raw bytes của chatbot, chỉ parse để persist ở cuối stream. |
| **Low** | `services/chatbot/app/workflow/retrieval.py:187-202` | Citation payload | `document_id` trùng `slide_id`, `title` chứa lại `lesson_title`, `location`/`pdf_url`/`page_number` chồng nhau | Gọn schema citation và lấy snippet on-demand thay vì nhúng 500 ký tự mỗi citation. |

## 2. Rủi ro độ chính xác model khi tối ưu

Các mục dưới đây là điều kiện **phải đo trước khi bật**, không phải khuyến nghị bật ngay.

1. **FP16 cho UniGaze (A).** Gaze là regression ra pitch/yaw; fp16 làm giảm độ chính xác biểu diễn và có thể lệch hệ số calibration. Rủi ro: sai số góc tăng, đặc biệt ở góc nhìn lớn, và calibration `lstsq` chỉ hấp thụ được lệch tuyến tính chứ không bù được sai số phi tuyến. Kiểm chứng: so pitch/yaw MAE và sai số trên màn hình (px) giữa fp32/fp16 trên cùng tập frame calibration, theo từng model; chỉ bật khi chênh lệch dưới ngưỡng chấp nhận và giữ cờ fallback.
2. **Giảm độ phân giải client 480 → 320 px (A).** BlazeFace và 6 keypoint mất độ chính xác dưới mức pixel, `solvePnP` nhạy với nhiễu landmark → warp lệch, gaze lệch vài độ. Kiểm chứng: đo phân bố sai số landmark, góc head-pose và khoảng cách gaze so với 480 px trên bộ frame có nhãn.
3. **Giảm chất lượng JPEG (A).** Artifact nén quanh vùng mắt/mí làm landmark và texture mống mắt biến dạng. Kiểm chứng: quét q = 0,6/0,7/0,78 và đo MAE gaze; ưu tiên giảm resolution trước khi giảm quality.
4. **Chuyển MediaPipe sang `RunningMode.VIDEO`/tracking (A).** Bỏ detect mỗi frame giúp giảm ~1,4 ms nhưng bbox có thể trễ khi quay đầu nhanh, crop lệch vài pixel → sai số góc. Kiểm chứng: replay video có cử động đầu nhanh, so landmark với chế độ detect từng frame; bắt buộc re-detect định kỳ hoặc khi IoU giảm.
5. **Batch nhiều session trên GPU (A).** ViT dùng LayerNorm nên về mặt toán học batch không đổi kết quả từng mẫu; rủi ro thực tế là thứ tự/kết quả lệch pha, padding sai và latency đuôi tăng. Kiểm chứng: so từng frame batch-1 với batch-N (sai khác phải ở mức nhiễu fp) và đo p99 chứ không chỉ p50.
6. **Giảm FPS hoặc ép `suggestedFps` (A).** Không làm sai từng điểm gaze nhưng làm giảm mật độ mẫu: `tracked_duration_ms`, `fixation_count`, `heatmap_grid` 24×24 và `aoi_stats` thưa hơn → số liệu phân tích của giáo viên kém ổn định. Cần ghi rõ ngưỡng FPS tối thiểu khi so sánh giữa các phiên.
7. **Giảm DPI render PDF cho VLM 150 → 110 (B).** Chữ nhỏ, bảng, số 0 đứng đầu và công thức LaTeX dễ bị đọc sai; transcript sai làm hỏng cả FTS lẫn embedding, tức giảm recall về sau. Kiểm chứng: so transcript trên bộ slide có bảng/công thức, đo CER và tỉ lệ giữ nguyên số.
8. **Đổi PNG → JPEG cho ảnh gửi VLM (B).** Artifact trên nét chữ mảnh; cùng loại rủi ro như trên nhưng nhẹ hơn. Kiểm chứng bằng diff transcript trên cùng bộ slide.
9. **Quantize/ONNX int8 cho Qwen3-Embedding (B, C).** Vector đổi hình học, ngưỡng cosine 0,2 và trọng số RRF hiện tại không còn hiệu lực tương đương. Bắt buộc đo recall@8 và MRR so với fp32 trên bộ câu hỏi thật trước khi đổi; giữ nguyên chiều 1024 và `normalize_embeddings`.
10. **Tăng batch embedding (B).** Cùng model, cùng `max_length`, cùng pooling thì kết quả không đổi về lý thuyết; rủi ro nằm ở chỗ vô tình đổi truncation hoặc padding khiến vector khác. Kiểm chứng: so cosine giữa vector batch-1 và batch-8, phải xấp xỉ 1,0.
11. **Chunk slide thay vì 1 slide = 1 vector (B, C).** Hiện transcript dài bị cắt âm thầm theo `max_seq_length`; chunk có thể tăng recall nhưng làm citation trùng lặp và một slide có thể chiếm hết top-k. Cần dedupe citation theo `slide_id` và giới hạn số chunk/slide.
12. **Đổi sang HNSW thật hoặc hạ `ef_search` (C).** `ef_search` thấp làm giảm recall; với `course_id` lọc sau index, số row trả về có thể thiếu `LIMIT` nên câu trả lời mất nguồn đúng. Kiểm chứng: so recall@8 với exact search trên cùng corpus, và theo dõi tỉ lệ `insufficient_evidence`.
13. **Bỏ threshold khỏi `WHERE` (C).** Giữ threshold nhưng lọc sau `LIMIT` cho kết quả gần tương đương và planner tốt hơn; nếu bỏ hẳn threshold, nhiễu tăng. Giữ ngưỡng 0,2 như bộ lọc sau cùng và đo lại tập nguồn được trích.
14. **Cache retrieval/answer (C).** Rủi ro chính là **stale sau khi sửa nội dung**: `pipeline_version` đang hardcode `rag-v2` và không đổi khi đổi prompt/model VLM, nên cache phải key theo `updated_at`/hash nội dung, không chỉ theo câu hỏi.
15. **Giảm `RAG_TOP_K` hoặc cắt context (C).** Giảm prompt giúp TTFT nhưng dễ mất nguồn cần thiết; đo `verified`/`citation_failed` và độ đầy đủ câu trả lời trước khi hạ.
16. **Tắt HyDE/rewrite (C).** Giảm 1 LLM call nhưng giảm recall với câu hỏi ngắn, mơ hồ và follow-up; A/B theo nhóm câu hỏi, không tắt toàn cục.
17. **Skip slide không đổi bằng hash (B).** Chỉ an toàn nếu hash bao gồm nội dung trang PDF **và** version prompt/model VLM; nếu không sẽ giữ transcript cũ sau khi đổi pipeline.
18. **Đổi model/prompt VLM (B).** `pipeline_version` hardcode và `model_version` chỉ ghi embedding → đổi VLM không tự đánh dấu stale. Phải bump version và reindex có chọn lọc, nếu không RAG trộn nội dung sinh bởi 2 pipeline khác nhau.

## 3. Cần đo thêm runtime

1. **Batch gaze xuyên session.** Dựng 8-16 phiên, batch 4-8 frame/forward, đo `gpu_ms` p50/p99, SM utilization, VRAM và tỉ lệ drop; xác nhận batch không làm tăng p99 do phải chờ gom frame.
2. **A/B fp16 cho UniGaze.** Trên cùng bộ frame calibration: MAE pitch/yaw, sai số px trên màn hình, tỉ lệ `no_face` và hệ số calibration trước/sau; tách theo góc nhìn.
3. **Trần ingest thật.** 100 slide: đo wall theo từng stage (render/VLM/embed/DB) với `cpus` 1 vs 4 cho embedding-worker và batch 1/8/16; xác định stage nào thành trần sau khi sửa.
4. **Recall retrieval trước/sau khi đổi query shape.** So exact search (không index) với HNSW + `ef_search` 40/80/160 trên bộ câu hỏi có nhãn; đo recall@8, MRR và tỉ lệ citation hợp lệ.
5. **TTFT attribution.** Instrument theo mốc: rewrite xong, embedding xong, SQL xong, token đầu của LLM, token đầu tới client; tách phần gate 200 từ và phần prefill prompt để biết nên cắt context hay đổi gate.

## 4. Ghi chú phạm vi

- Phần này kết luận cho nội bộ `services/gaze` và `services/chatbot`, gồm tài nguyên cấp cho 2 service; backend route, DB, worker backend và nginx đã ở Phần 1.
- Các số baseline lấy từ `benchmarks/baseline/20261120T180000Z-baseline/` trên RTX 3060 (fp32, 1 replica gaze) và stack benchmark cô lập; số production có thể khác do GPU/LLM provider.
- Không có thay đổi code nào được thực hiện; các truy vấn kiểm tra chỉ đọc (`EXPLAIN`, `pg_stat_user_indexes`, `SHOW`).

---

# Perf audit — Phần 3: Frontend (load, gaze real-time, slide + RAG)

> Tiếp nối Phần 1 (Backend & DB) và Phần 2 (2 AI services). Phạm vi: Next.js 16 App Router trong `frontend/`: bootstrap/SSR, gaze tracker + WebSocket + overlay, PDF slide viewer, chat SSE + Markdown/KaTeX, và phần coupling giữa chat với AOI snapshot.
> Nguồn: code hiện tại, build production trong `frontend/.next` (BUILD_ID 2026-11-20), và đo header asset qua nginx local. Không sửa code.
> Số đo bundle là của build hiện có, gzip level 6 (cùng mức `nginx/nginx.conf:65`); không phải số liệu production.

## 0. Luồng đã trace

```text
Flow 1 — Tải trang ban đầu
  HTML/RSC shell → hydrate Providers (QueryClient) → AppShell (useAuthState)
    → useMyEnrollments / useTeacherCourses / useCourseOutline
    → (reader) useCourseVisit → POST /api/course-visits
              → POST /api/learning-sessions
              → GET /api/learning-sessions/{id}/contents
              → POST /api/learning-sessions/{id}/presentations
              → POST /api/presentations/{id}/layouts
              → PdfPage: GET PDF → getPage → canvas render

Flow 2 — Real-time gaze
  getUserMedia(640×480) → <video> → canvas.drawImage
    → toBlob(image/jpeg, 0.78) → blob.arrayBuffer() → copy header+JPEG
    → WS /gaze/session/{id}/stream
    → gaze service: MediaPipe (CPU) → UniGaze (GPU) → JSON {x,y,status,suggestedFps}
    → transformGazeToViewport() → onPoint() (chấm gaze) + onFrame() (buffer)
    → flush 1.5 s / 40 sample → IndexedDB → POST /gaze-batches

Flow 3 — Slide + RAG
  Đổi slide → createPresentation POST → useAoiSnapshot POST /layouts → PdfPage render
  Mở chat  → layoutKey đổi + slide co lại → PDF repaint + /layouts mới + flush gaze
  Gửi câu  → POST /api/courses/{id}/chat/stream (SSE)
           → onToken → setStreamingText → ReactMarkdown + KaTeX parse lại toàn bộ
           → scrollIntoView smooth → scroll event → measureAoiRects → có thể /layouts mới
  Citation → cùng bài: setCurrentSlide; khác bài: đổi lesson → session → slides → mới nhảy slide
```

## 1. Số đo nhanh trên build hiện có

| Route | Script ban đầu | JS raw | JS gzip | Ghi chú |
|---|---:|---:|---:|---|
| `_not-found` (shell tham chiếu) | 12 | 688 KB | 210 KB | Root layout + error/not-found boundary |
| `/` | 13 | 715 KB | 220 KB | Landing |
| `/student` | 17 | 846 KB | 265 KB | + AppShell/Topbar/Radix |
| `/teacher` | 16 | 831 KB | 259 KB | |
| `/admin` | 17 | 851 KB | 266 KB | |
| `/account/login` | 16 | 786 KB | 245 KB | |
| `/try` | 15 | 757 KB | 234 KB | Đã gồm calibration + gaze tracker |

Asset đáng chú ý (đo trực tiếp):

| Asset | Raw | Gzip | Cache-Control hiện tại |
|---|---:|---:|---|
| `globals.css` | 99 KB | 17 KB | render-blocking, mọi route |
| Font preload (3 file) | 85 KB | — | `font-display: swap`, preload mọi route |
| Icon registry chunk (`1ezb8gmqwd76o.js`) | 48 KB | 11 KB | immutable, nhưng có trên **mọi** route |
| PDF.js chunk (`238z5qi80r8h8.js`) | 412 KB | 120 KB | lazy, nằm trên critical path slide đầu |
| KaTeX/chat chunk (`3w3eht99kyewv.js`) | 435 KB | 129 KB | lazy, tải lần đầu mở chat |
| `pdf.worker.min.mjs` | 1.08 MB | 299 KB | `public, max-age=0` (đã kiểm tra header) |

## 2. Bảng điểm nghẽn

### 2.1 Tải trang ban đầu

| Impact | File:Dòng | Luồng bị ảnh hưởng | Nguyên nhân gốc rễ | Hướng tối ưu đề xuất (1 dòng) |
|---|---|---|---|---|
| **High** | `L01` · `frontend/app/student/page.tsx:12-14`, `teacher/page.tsx:23-25`, `student/courses/[courseId]/page.tsx:11-13`, `calibrate/page.tsx:11-13` + `useSearchParams` tại `course-browser.tsx:148`, `teacher-course-list.tsx:75`, `reader-content.tsx:70` | 1, 3 | `useSearchParams()` buộc Suspense boundary bailout sang CSR; fallback `null` nên HTML chỉ có shell + `<template data-dgst="BAILOUT_TO_CLIENT_SIDE_RENDERING">`, không skeleton/list (đã kiểm tra `student.html`). | Fallback skeleton thật + `loading.tsx`, hoặc tách `useSearchParams` vào component con để phần còn lại vẫn SSR. |
| **High** | `L02` · `frontend/components/student/learning-reader/reader-content.tsx:73-77,190-194,278-338,354-357,436-505,521-534` + `frontend/hooks/use-course-visit.ts:67-105` + `frontend/lib/api/aoi.ts:126-157` | 1, 3 | Chuỗi phụ thuộc outline/enrollments → visit → session → contents → presentation → layout; mỗi bước chờ RTT trước, chưa tính PDF (S03). | Trả `enrollmentId`/visit trong outline, gộp visit+session, prefetch outline/slides từ course list. |
| **Med** | `L03` · `frontend/components/layout/app-shell.tsx:1-28` + `frontend/components/student/student-home.tsx:1-7` + `frontend/components/teacher/teacher-course-list.tsx:1-7` + `frontend/components/student/learning-reader/index.tsx:1-12` | 1 | Toàn bộ data dashboard fetch client sau hydrate, không RSC prefetch/`HydrationBoundary`; `/student` cần 265 KB gzip JS trước khi có data. | Fetch trang đầu ở RSC/route handler và hydrate, hoặc prefetch query song song với route chunk. |
| **Med** | `L04` · `frontend/hooks/use-student.ts:27-38` + `reader-content.tsx:354-357` + `frontend/lib/api/student.ts:90-96` | 1, 3 | Query key đổi khi có `sessionId` nên gọi `/lessons/{id}/contents` rồi `/learning-sessions/{id}/contents`; `placeholderData` chỉ che loading, không chặn request thứ hai. | Chỉ dùng endpoint session-aware, hoặc seed `initialData` từ dữ liệu lesson đã có. |
| **Med** | `L05` · `frontend/components/ui/icon.tsx:4-75,77-148` + `frontend/app/error.tsx:3-4` + `frontend/app/not-found.tsx:3` | 1 | 70 icon static import + registry `string → component` nên bundler không tree-shake; error/not-found kéo chunk vào mọi route (48 KB raw / 11 KB gzip). | Import trực tiếp theo nơi dùng; error/not-found dùng SVG inline. |
| **Med** | `L06` · `frontend/components/layout/topbar.tsx:9,78-83` + `frontend/components/layout/user-menu.tsx:7-14,32-49` | 1 | Radix `Sheet` và `DropdownMenu` luôn nằm trong initial bundle dù đang đóng; khoảng 30 KB gzip chrome trên mọi route đã đăng nhập. | Dynamic import drawer khi `mobileOpen`, lazy menu content sau trigger avatar. |
| **Med** | `L07` · `frontend/hooks/use-stored-user.ts:35-41` + `frontend/hooks/use-profile.ts:8-13` + `frontend/components/profile/profile-page.tsx:276` | 1 | Cùng gọi `GET /api/me/profile` dưới hai key `["auth","user"]` và `["me","profile"]` → 2 request ở trang hồ sơ. | Dùng một query key và `select` ra `AuthUser`. |
| **Med** | `L08` · `frontend/app/layout.tsx:7-8,26` | 1 | Hai font family; Next preload 3 file woff2 (10 + 47 + 28 KB) trên mọi route, trong khi Geist chỉ dùng cho heading. | Bỏ Geist hoặc `preload:false`; giữ một family. |
| **Med** | `L09` · `frontend/components/courses/course-browser.tsx:79-81` + `frontend/components/teacher/teacher-course-list.tsx:26-28` + không có `frontend/app/**/loading.tsx` | 1, 3 | Mọi course link dùng `prefetch={false}`, route đích CSR + fallback null, không có loading boundary → click course phải chờ chunk + data, không feedback. | Bỏ `prefetch={false}` cho link chính và thêm `loading.tsx` skeleton. |
| **Med** | `L10` · `frontend/components/try/try-flow.tsx:8-10` + `frontend/app/try/page.tsx:1-4` | 1 | `TryFlow` static import `CalibrationStage`, `useCalibration`, `useGazeTracker`; màn intro chỉ cần nút nhưng vẫn tải code camera/calibration (~13.6 KB gzip). | Dynamic import các step calibrate/view/result. |
| **Med** | `L11` · `reader-content.tsx:75` + `frontend/hooks/use-student.ts:12-17` + `frontend/lib/api/student.ts:82-84` | 1, 3 | Reader cần đúng một `enrollmentId` nhưng tải toàn bộ `/api/me/enrollments`. | Trả `enrollmentId` trong course outline hoặc thêm endpoint riêng. |
| **Med** | `L12` · `frontend/lib/pdf/pdfjs.ts:10` + `frontend/public/pdf.worker.min.mjs` + `nginx/default.conf:214-243` | 1, 3 | Worker 1.08 MB (299 KB gzip) và `/pdfjs/*` nằm ngoài `/_next/static` nên `Cache-Control: max-age=0`, phải revalidate mỗi lần; static chunk thì immutable. | Hash đường dẫn hoặc set immutable cho worker/cmaps. |
| **Med** | `L13` · `frontend/lib/api/client.ts:78-82,218-231` | 1, 3 | GET cũng gắn `Content-Type: application/json` (preflight nếu `NEXT_PUBLIC_API_URL` khác origin) và parse `document.cookie` mỗi request. | Chỉ set `Content-Type` khi có body; cache CSRF token. |
| **Med** | `L14` · `frontend/lib/api/client.ts:193-238` + các hook `frontend/hooks/use-student.ts:12-38` | 1, 3 | `queryFn` không nhận/không truyền `signal`, nên request không abort khi unmount/đổi key. | `queryFn: ({signal}) => apiFetch(..., {signal})` cho mọi query. |
| **Med** | `L15` · `frontend/app/providers.tsx:7-11` | 1 | `subscribeAuthChange(() => client.clear())` xoá toàn bộ cache khi session hết hạn → mọi query đang mount refetch đồng loạt. | Chỉ xoá auth query và invalidate có chọn lọc. |
| **Med** | `L16` · `frontend/components/layout/topbar.tsx:35` | 1 | `sticky` + `backdrop-blur-sm` khiến trình duyệt composite lại vùng blur mỗi lần scroll ở các trang dùng AppShell. | Bỏ blur hoặc dùng nền đặc. |
| **Med** | `L17` · `frontend/components/landing/landing-v2.css:4,13` | 1 | Landing dùng `backdrop-filter: blur(18px)`, `filter: blur(7px)` và nhiều radial-gradient/box-shadow lớn trên trang dài → paint/composite nặng lần đầu. | Giảm blur, thay bằng asset tĩnh/pre-render. |
| **Med** | `L18` · `reader-content.tsx:340-342` + `frontend/lib/gaze-sender.ts:17-38,40-45,76-97` | 1, 2 | `flushGazeQueue()` on mount luôn gọi `/api/health` trước khi kiểm tra queue rỗng. | Check `pendingGazeBatches()` trước, chỉ gọi health khi có batch; cache generation. |
| **Med** | `L19` · `frontend/components/student/preflight-check/index.tsx:40,55-118` | 1 | Status gaze/calibration chạy tuần tự sau `setTimeout(0)`; cộng profile + outline thành nhiều RTT trước khi hiện CTA. | Chạy song song bằng query cache, bỏ `setTimeout(0)`. |
| **Med** | `L20` · `frontend/lib/api/client.ts:63-75,176-191,233` + `frontend/app/providers.tsx:13-31` | 1 | Access token cookie có TTL 60 phút (`backend/app/services/auth_flow.py:87`); sau khi hết hạn, N query đang mount cùng nhận 401 trước khi refresh xong. `inFlightRefresh` dedupe refresh nhưng không tránh N request 401; hard reload trong 60 phút không dính vì backend fallback cookie `access_token` (`backend/app/api/deps.py:24-32`). | Refresh chủ động trước expiry hoặc gate query protected đến khi auth ready. |

### 2.2 Luồng real-time (camera → WS → eye-tracking → vẽ)

| Impact | File:Dòng | Luồng bị ảnh hưởng | Nguyên nhân gốc rễ | Hướng tối ưu đề xuất (1 dòng) |
|---|---|---|---|---|
| **High** | `R01` · `reader-content.tsx:94,611-621` + `frontend/components/student/learning-reader/reader-view.tsx:97-151,163-186` | 2 | `setGazeDot` mỗi frame 15–60 Hz làm re-render toàn bộ `ReaderContent` → `ReaderView` → `ReaderFrame` (outline, PDF wrapper, quiz, chat panel); `ReaderView`/`ReaderFrame` không memo và JSX children (`slideContent`, `chatPanel`, `banners`) được tạo mới mỗi render. | Tách chấm gaze thành component lá dùng ref/store và cập nhật `transform` trực tiếp, không giữ state trong `ReaderContent`. |
| **High** | `R02` · `frontend/hooks/use-gaze-tracker.ts:345-359,462-476,394-405` | 2 | `attempts` bị reset về 0 mỗi lần `onopen`; khi server đóng bằng `1008 not_calibrated` / `1013 pipeline_not_ready` (session hết hạn sau 30 phút không frame, gaze service restart, pipeline chưa ready) hoặc close do mạng, vòng lặp luôn chờ ~750 ms rồi mở lại, `MAX_RECONNECTS` không bao giờ đạt; UI vẫn báo "Gaze hoạt động". | Chỉ reset budget sau khi socket sống ≥10 s; coi 1008/1013 là fatal → clear session và yêu cầu hiệu chỉnh lại. |
| **High** | `R03` · `use-gaze-tracker.ts:282-284` + `reader-content.tsx:604-610,625-627` | 2 | Không có send-gate; vẫn capture/send frame với `presentationId:null` hoặc layout cũ trong mỗi lần đổi slide/layout/resize; gaze service vẫn chạy MediaPipe + UniGaze rồi backend mới bỏ. | Thêm `shouldSend()`/require presentation, bỏ capture+send khi `aoiReady=false`. |
| **High** | `R04` · `frontend/hooks/use-aoi-snapshot.ts:144-161,201-221,265-283` + `frontend/lib/aoi/measure.ts:17-30` + `frontend/components/assistant/study-assistant-chat/message-bubble.tsx:29-41` + `reader-content.tsx:426,405-408,521-534` | 2, 3 | `rectsKey` chứa rect của **mọi** `[data-aoi]` gồm từng bubble chat; listener `scroll` capture toàn window và chat open đổi `layoutKey` → POST `/layouts` mới, `ready=false`, flush batch, tăng `layoutGeneration`, gaze bị tạm dừng. | Loại chat khỏi layout key/observer, chỉ snapshot khi hình học slide đổi, không flush gaze cho chat scroll. |
| **High** | `R05` · `use-gaze-tracker.ts:197-217,309-322` | 2 | Mỗi frame `drawImage` + `toBlob` JPEG + `blob.arrayBuffer()` + tạo `Uint8Array` mới và copy header+JPEG trên main thread ở 15–60 fps. | `OffscreenCanvas` + worker, gửi `Blob` ghép header không copy, tái dùng buffer/encoder. |
| **Med** | `R06` · `use-gaze-tracker.ts:201,215` + `services/gaze/app/services/preprocessing.py:17` | 2 | Capture 480 px / quality 0.78 trong khi model warp về 224×224 → 300–450 KB/s upload và encode dư. | Config capture 320 px / 0.6, đo lại accuracy và băng thông trước khi giữ 480/0.78. |
| **Med** | `R07` · `use-gaze-tracker.ts:336-341` + `services/gaze/app/settings.py:40-50` + `services/gaze/app/api/session.py:231-236` | 2 | Lịch gửi tính theo `interval - elapsed` của lần send trước → jitter; server drop frame đến gần hơn 85% interval, nên client đã tốn capture/upload rồi vẫn mất frame. | Lịch tuyệt đối `nextAt += interval`, không gửi sớm hơn ngưỡng server. |
| **Med** | `R08` · `use-gaze-tracker.ts:231-254,345-359` | 2 | Không có watchdog cho handshake; nếu `onopen` không bao giờ tới (proxy/NAT), promise treo, camera bật, UI báo hoạt động nhưng không gửi frame. | Timeout mở 5 s → close/retry, expose trạng thái degraded. |
| **Med** | `R09` · `frontend/lib/gaze-queue.ts:80-92,164-181,236-251` + `frontend/lib/gaze-sender.ts:40-74` | 2 | Mỗi thao tác IndexedDB `open` rồi `close`; `pendingGazeBatches` dùng `getAll()` toàn bộ batch rồi filter bằng JS, không có index `sessionId`. | Giữ singleton `IDBDatabase`, thêm index `sessionId`, delete theo key. |
| **Med** | `R10` · `reader-view.tsx:178-183` + `frontend/components/try/try-flow.tsx:293-297` | 2 | Chấm gaze đặt bằng `left/top %` → layout/paint mỗi tick, không được promote layer. | `transform: translate3d(...)` + `will-change: transform`. |
| **Med** | `R11` · `frontend/hooks/use-display-guard.ts:230-236,261-275` + `:50-58` | 2 | Wheel listener non-passive trên window, `visualViewport` scroll gọi `evaluate()` mỗi event, `matchMedia` tạo mới mỗi lần đo, poll 500 ms. | Chỉ gắn wheel non-passive trong reader container, cache `MediaQueryList`, giảm poll. |
| **Med** | `R12` · `frontend/components/student/preflight-check/index.tsx:153-163,172-197` | 2 | Camera 1280×720, chụp full-frame JPEG quality 0.88 chỉ để check face; stream vẫn chạy sau check (chỉ stop khi unmount). | Hạ 640×480/quality 0.8 và stop track ngay sau check. |
| **Med** | `R13` · `frontend/hooks/use-calibration.ts:190-212,224-247` | 2 | `getUserMedia` không constrain width/height (có thể 1080p/4K), video ẩn decode suốt phiên calibration. | Constrain 640×480, stop track sau train. |
| **Med** | `R14` · `use-aoi-snapshot.ts:216` + `frontend/lib/api/aoi.ts:144-157` | 2, 3 | POST layout không có `AbortSignal`/coalescing; `ready` giữ false đến khi request xong (timeout 30 s) → gaze pause dài nếu mạng chậm. | Giữ request mới nhất + abort cũ, timeout ngắn. |
| **Med** | `R15` · `reader-content.tsx:418-423` | 2 | Resize gọi `pauseAndFlushGaze()` mỗi event, không debounce; buffer rỗng sau lần đầu nhưng refs/state work lặp suốt chuỗi resize. | rAF hoặc debounce 100 ms. |
| **Med** | `R16` · `frontend/components/try/try-flow.tsx:86,100-107` | 2 | Hai `setState` mỗi frame → re-render cả trang demo; `gazeRef` tăng không giới hạn. | Giữ dot/count trong ref, chỉ `setState` khi xem kết quả. |
| **Med** | `R17` · `use-gaze-tracker.ts:59-81,294-308,361-392` | 2 | Mỗi frame đọc `window.innerWidth/innerHeight/screenX/screenY` (layout-dependent), `new Date().toISOString()`, `JSON.parse`, cấp phát object. | Cache viewport trong ref theo resize, giảm cấp phát. |

### 2.3 Slide / PDF viewer

| Impact | File:Dòng | Luồng bị ảnh hưởng | Nguyên nhân gốc rễ | Hướng tối ưu đề xuất (1 dòng) |
|---|---|---|---|---|
| **High** | `S01` · `frontend/components/pdf/pdf-page.tsx:110-120` + `frontend/components/student/learning-reader/reader-slide-content.tsx:62-69` | 3 | `page.render({ canvas })` paint full-resolution trên main thread, không `OffscreenCanvas`/bitmap cache; đổi slide, resize, mở chat đều repaint. | Render vào `OffscreenCanvas`/worker hoặc cache `ImageBitmap` theo `(url,page,size)` và chỉ blit khi cần. |
| **High** | `S02` · `frontend/components/reader/reader-frame/index.tsx:251` + `frontend/components/assistant/study-assistant-chat/index.tsx:330` + `reader-slide-content.tsx:56-69` + `pdf-page.tsx:148-164` + `reader-content.tsx:426` | 3 | Chat là flex item làm slide co; `ResizeObserver` cancel render, clear canvas và repaint ở size mới; đồng thời `layoutKey` đổi → `/layouts` mới + flush gaze. | Giữ canvas ở pixel cố định và CSS-scale, hoặc bỏ repaint nếu letterbox được từ bitmap cache. |
| **High** | `S03` · `frontend/lib/pdf/pdfjs.ts:32-45` + `pdf-page.tsx:91-95` + `use-aoi-snapshot.ts:175-179` + `frontend/components/assistant/study-assistant-chat/citation-list.tsx:73-88` | 3 | `disableRange`/`disableStream` buộc tải cả PDF trước `getPage`; layout/gaze chờ `data-pdf-width`; citation preview cũng tải cả deck cho một trang, dù nginx local đã trả `Accept-Ranges: bytes` (`backend/app/api/routes/media.py:51-61`). | Bật Range khi backend hỗ trợ, hoặc trả ảnh trang/thumbnail; hiện thumbnail trang đầu trước. |
| **Med** | `S04` · `pdf-page.tsx:137-164` | 3 | Render effect chạy lần đầu, rồi `observe(container)` giao initial observation; callback không so size cũ, luôn `setReady(false); render()` sau 80 ms → render lần hai cancel lần một. | Lưu size đã render, bỏ callback trùng; bắt đầu observe sau paint đầu. |
| **Med** | `S05` · `pdf-page.tsx:110-114` | 3 | Canvas = CSS × DPR không cap; DPR 3 trên vùng 1120×630 → 25–45 MB mỗi canvas. | Cap DPR 2 cho slide/preview. |
| **Med** | `S06` · `reader-slide-content.tsx:62-69` + `pdf-page.tsx:75-135` | 3 | `key={pageKey}` remount `PdfPage` mỗi slide; không cache bitmap nên quay lại slide cũ phải `getPage` + render lại. | LRU bitmap theo `(url,page,width)` hoặc giữ vài canvas gần nhau. |
| **Med** | `S07` · `pdfjs.ts:17-18,53-59` | 3 | `MAX_DOCUMENTS = 4`, destroy không ref-count; có thể destroy document đang được canvas dùng → lỗi/parse lại toàn bộ. | Ref-count document đang mở hoặc LRU theo lesson active. |
| **Med** | `S08` · `use-aoi-snapshot.ts:157-180` | 3 | PDF chưa có `data-pdf-*` → `schedule()` retry mỗi 250 ms vô hạn; mỗi pass đo toàn bộ `[data-aoi]` (gồm chat) trong lúc PDF đang tải. | `PdfPage` phát ready event, backoff + giới hạn số lần. |

### 2.4 Chat streaming / RAG

| Impact | File:Dòng | Luồng bị ảnh hưởng | Nguyên nhân gốc rễ | Hướng tối ưu đề xuất (1 dòng) |
|---|---|---|---|---|
| **High** | `C01` · `frontend/components/assistant/study-assistant-chat/index.tsx:241-245` | 3 | `onToken` gọi `setStreamingText` mỗi token → re-render `StudyAssistantChat`, header, session menu, `MessageList`, mọi bubble. | Publish token qua external store/rAF batch, chỉ bubble streaming re-render. |
| **High** | `C02` · `message-bubble.tsx:45-52` + `.../markdown.tsx:42-74` + `frontend/lib/chat-markdown.ts:5-10` | 3 | Mỗi token chạy `normalizeMath()` trên toàn chuỗi, rồi `remarkGfm` + `remarkMath` + `remarkCitations`, rồi `rehypeKatex` trên toàn message → O(n²) main thread. | Render plain text khi streaming, parse Markdown một lần ở `onDone` hoặc throttle 100–200 ms; hoist plugin arrays. |
| **High** | `C03` · `index.tsx:156-159` | 3 | Effect phụ thuộc `streamingText` nên gọi `scrollIntoView({behavior:"smooth"})` mỗi token; scroll event lại feed AOI listener. | `container.scrollTop = scrollHeight` trong rAF, chỉ khi `nearBottom`, `behavior:"auto"`. |
| **Med** | `C04` · `message-list.tsx:72-82` + `frontend/lib/api/chat.ts:86-91` | 3 | Mount toàn bộ message (tới 200), mỗi message là Markdown/KaTeX DOM; mở session cũ mount đồng loạt. | Virtualize hoặc `content-visibility:auto` + phân trang lịch sử. |
| **Med** | `C05` · `message-list.tsx:73-81` + `message-bubble.tsx:9-21` | 3 | `MessageBubble` không memo và nhận `streamingText` đổi mỗi token → mọi bubble chạy lại wrapper/citation dù `Markdown` memo bail. | Memo với comparator bỏ `streamingText` cho message không pending; chỉ bubble pending nhận text. |
| **Med** | `C06` · `index.tsx:117,142-148,270` + `frontend/hooks/use-chat.ts:29-35` + `.../chat-helpers.ts:78-85` | 3 | Stream xong query bật lại + `staleTime:0` → refetch toàn history; `toUiMessages` tạo mảng `citations` mới → memo `Markdown` mất → parse lại mọi câu trả lời. | `setQueryData` bằng message cuối, giữ reference citations cũ. |
| **Med** | `C07` · `index.tsx:61,360-366` + `composer.tsx:44-51` | 3 | State `input` ở panel root → mỗi phím re-render `MessageList` và map toàn bộ message. | Đưa state vào `Composer`, memo `MessageList`. |
| **Med** | `C08` · `composer.tsx:39,47-50` + `use-aoi-snapshot.ts:265-280` | 3 | `onChange` ghi `style.height` rồi đọc `scrollHeight` (forced reflow); form có `data-aoi` và observer theo dõi `style` → typing schedule measure/layout. | Dùng `field-sizing: content` hoặc debounce; loại composer khỏi AOI observer. |
| **Med** | `C09` · `panel-header.tsx:44-50` + `session-list.tsx:58-70` | 3 | `sessions.map(...)` dựng lại mỗi token/phím dù dropdown đang đóng. | Chỉ render menu content khi open và memo theo `sessions`. |
| **Med** | `C10` · `frontend/lib/api/client.ts:245-263` + `frontend/lib/api/chat.ts:214-237` | 3 | `apiFetchStream` không có timeout; nếu backend/proxy stall, `reader.read()` treo, `streaming` mãi true, composer bị disable. | Idle watchdog reset theo chunk hoặc `AbortSignal.timeout` cho stream. |
| **Med** | `C11` · `index.tsx:76-81,119-138` | 3 | Đóng panel không abort SSE; panel vẫn mounted `open=false`, stream tiếp tục đọc và setState nền. | Abort khi `open=false` hoặc detach UI updates khỏi stream. |
| **Med** | `C12` · `frontend/hooks/use-student.ts:37` + `reader-content.tsx:436-505` | 3 | `placeholderData: previous` giữ slides bài cũ khi đổi lesson; nếu session resolve trước slide mới → tạo presentation sai slide rồi tạo lần hai. | Không placeholder cross-lesson; chờ `slides` thuộc `activeLessonId`. |
| **Med** | `C13` · `frontend/hooks/use-chat.ts:102-110` + `use-reader-chat.ts:19,23-25,48` + `study-assistant-chat/index.tsx:54` | 3 | Access `staleTime:0`, `refetchOnWindowFocus:"always"`, poll 5 s, 2 observer; `refetch()` chạy cả khi `enabled:false`; `toggleChat` await refetch rồi panel mount refetch lần nữa. | `staleTime` 60 s, bỏ mount refetch/await, chỉ poll khi panel mở. |
| **Med** | `C14` · `use-reader-chat.ts:27-30` + `use-chat.ts:109` | 3 | `retry:false` + `chatAllowed=false` với mọi lỗi → panel tự đóng khi mạng chập, đổi layout key, PDF repaint và tạo layout snapshot mới. | Chỉ đóng khi 403/deny rõ ràng, không đóng vì lỗi mạng tạm thời. |
| **Med** | `C15` · `frontend/components/assistant/lazy-study-assistant-chat.tsx:11-22` | 3 | Chunk chat + Markdown + KaTeX (129 KB gzip) chỉ tải khi mở lần đầu, không prefetch. | Prefetch idle/hover hoặc tách panel shell khỏi Markdown. |
| **Med** | `C16` · `reader-content.tsx:726-747,362-370` | 3 | Citation khác bài phải đổi bài → session → slides → mới nhảy slide, không có optimistic navigation. | Điều hướng optimistic bằng dữ liệu citation, đồng bộ session ở nền. |
| **Med** | `C17` · `frontend/components/assistant/assistant-context.tsx:64-83` + `frontend/components/quiz/inline-quiz/index.tsx:98-107` | 3 | Mỗi câu trả lời đưa `draftAnswers` vào context chung → provider value đổi → `ReaderContent` và cả cây reader re-render. | Tách draft context/selector, chỉ update mode/attempt. |
| **Med** | `C18` · `frontend/lib/aoi/measure.ts:17-30` + `frontend/lib/aoi/snapshot-key.ts:22-28` | 3 | Payload `/layouts` chứa rect của mọi bubble chat và gửi lại toàn bộ mỗi snapshot; tăng tuyến tính theo lịch sử hội thoại. | Chỉ gửi rect cấu trúc/UI tĩnh, hoặc gửi delta. |

## 3. Nhóm lỗi có thể sửa độc lập

**Đọc theo thứ tự:** R01/R04/C01/C02 + S03 là những đòn bẩy lớn nhất. Các nhóm dưới đây chia theo file ownership để có thể làm PR riêng; các nhóm cùng chạm `reader-content.tsx` cần merge tuần tự hoặc tách hunk.

### G1 — P0: Tách gaze overlay khỏi cây reader (R01, R10, R16)
- File: `reader-content.tsx` (state `gazeDot` + `onPoint`), `reader-view.tsx`, thêm `gaze-dot-layer.tsx`, `try-flow.tsx`.
- Vì sao độc lập: không đụng network/PDF/chat; chỉ thay cách truyền toạ độ.
- Test: bật `showGazeDot`, xác nhận `ReaderFrame` không re-render theo frame (React Profiler hoặc render counter tạm), dot bám đúng, `./scripts/e2e.sh`.

### G2 — P0: WebSocket lifecycle & send-gate (R02, R03, R07, R08)
- File: `use-gaze-tracker.ts`.
- Vì sao độc lập: chỉ sửa tracker, không đổi payload/contract.
- Test: giả lập close `1008`/`1013` và handshake treo → không reconnect storm, có trạng thái degraded; khi `presentationId=null` không gửi frame; `./scripts/test_gaze.sh fast`.

### G3 — P0: Capture pipeline & queue (R05, R06, R09, R17)
- File: `use-gaze-tracker.ts` (+ worker mới), `lib/gaze-queue.ts`.
- Test: đo CPU/upload trước-sau, kiểm tra frame vẫn đúng header v2 và batch/sequence; `./scripts/test_gaze.sh fast`; test offline queue.

### G4 — P0: Ổn định AOI snapshot (R04, R14, R15, C08, C18)
- File: `use-aoi-snapshot.ts`, `lib/aoi/measure.ts`, `lib/aoi/snapshot-key.ts`, `reader-content.tsx`, `composer.tsx`.
- Vì sao độc lập: chỉ ảnh hưởng layout snapshot/flush, không đổi API.
- Test: mở chat + cuộn 10 lần → 0 POST `/layouts`, không flush gaze, `layoutGeneration` không đổi; `./scripts/e2e.sh`.

### G5 — P0: Render khi stream chat (C01–C05, C07, C09, C17)
- File: `study-assistant-chat/index.tsx`, `message-list.tsx`, `message-bubble.tsx`, `markdown.tsx`, `composer.tsx`, `lib/chat-markdown.ts`.
- Test: `E2E_CHAT=1 ./scripts/e2e.sh`; câu trả lời >2.000 token; đo long task/INP và số lần parse Markdown.

### G6 — P1: Network/session hygiene của chat (C06, C10–C16)
- File: `use-chat.ts`, `use-reader-chat.ts`, `lazy-study-assistant-chat.tsx`, `reader-content.tsx` (citation), `lib/api/client.ts` (stream timeout).
- Test: đếm request khi mở/đóng/gửi 5 câu; SSE stall phải timeout; đóng panel phải abort; `E2E_CHAT=1 ./scripts/e2e.sh`.

### G7 — P1: PDF pipeline (S01–S08)
- File: `lib/pdf/pdfjs.ts`, `pdf-page.tsx`, `reader-slide-content.tsx`, `citation-list.tsx`, `nginx/default.conf` (cache), `next.config.ts`.
- Test: TTFB slide đầu, RAM canvas, chuyển slide liên tục, resize/mở chat; `./scripts/e2e.sh`.

### G8 — P1: Bootstrap reader & auth (L02, L04, L11, L14, L18, L20; C12)
- File: `lib/api/client.ts`, `app/providers.tsx`, `use-student.ts`, `reader-content.tsx`, `use-course-visit.ts`, `lib/api/aoi.ts`.
- Test: waterfall Network tab chỉ 1 lần `/contents`; hard reload sau 60 phút chỉ 1 refresh; `./scripts/e2e.sh`.

### G9 — P2: Bundle & SSR ban đầu (L01, L03, L05–L10, L12, L13, L15–L17)
- File: các `app/**/page.tsx`, `loading.tsx`, `icon.tsx`, `topbar.tsx`, `user-menu.tsx`, `use-stored-user.ts`/`use-profile.ts`, `app/layout.tsx`, `app/providers.tsx`, `lib/pdf/pdfjs.ts`, `lib/api/client.ts`, `landing-v2.css`.
- Test: `npm run analyze`; kiểm tra HTML có skeleton thay vì bailout; đo LCP `/student` và reader.

### G10 — P2: Preflight/calibration/demo (L19, R11, R12, R13, R16)
- File: `preflight-check/index.tsx`, `use-calibration.ts`, `try-flow.tsx`.
- Test: CPU khi mở preflight, số request status, camera stop sau check; thử `/try` trên máy yếu.

### G11 — P3: Ngoài 3 luồng (phụ lục X01–X06)
- File: teacher content/editor/replay.
- Test: `./scripts/e2e.sh` (teacher content, teacher analytics); đo số lần poll và canvas khi mở lesson nhiều slide.

**Thứ tự merge gợi ý:** G1 → G4 → G5 → G7 → G2 → G3 → G8 → G6 → G9 → G10. G1/G4/G8 cùng chạm `reader-content.tsx`; G5/C08 chạm `composer.tsx` nên tách khỏi G4 nếu muốn review nhanh.

## 4. Đã kiểm tra và **không** phải vấn đề

- **Auth hard reload:** backend fallback cookie `access_token` (`backend/app/api/deps.py:24-32`), nên hard reload trong 60 phút không tạo 401→refresh→retry; chỉ sau khi access cookie hết hạn (L20).
- **Core-js polyfill:** chunk `0cz1d0mv5g_q7.js` có `noModule=""` nên browser hiện đại không tải; chỉ legacy trả giá 109 KB raw / 38 KB gzip.
- **Backpressure gaze:** `bufferedAmount > 1 MB` được check trước capture (`use-gaze-tracker.ts:276-280`); send tuần tự, không có queue vô hạn phía client.
- **Cleanup:** WS handlers null + `close()`, camera tracks stop, timer clear, observer disconnect, prototype fullscreen được restore.
- **Một socket / một tracker:** `runWsSession` được await trong vòng lặp; StrictMode có thể xin camera hai lần nhưng stream đầu bị stop khi resolve.
- **Chấm gaze nằm ngoài observer:** `GazeDotOverlay` là sibling của `ReaderFrame` nên style per-frame không kích hoạt MutationObserver của `[data-aoi="reader-root"]`.
- **Canvas capture không scale DPR** là đúng (sample pixel gốc của video); DPR của PDF.js cũng đúng, chỉ thiếu cap.
- **Không có MediaPipe/ONNX/TensorFlow trong frontend**, inference hoàn toàn server-side.
- **Batch/rate nằm trong giới hạn:** 40 sample/batch so với max 2000; 40 req/phút so với 120/phút.
- **TanStack Query defaults hợp lý:** `staleTime 120 s`, `retry 1`, `refetchOnWindowFocus:false`; vấn đề nằm ở các override cục bộ (chat access/quiz) và duplicate key.
- **Lazy load đã có:** PDF.js, `LazyPdfPage`, chat + Markdown/KaTeX, quiz, `@dnd-kit` trong `ContentEditor` đều `dynamic()`.
- **Root layout không fetch data**, `QueryClient` tạo một lần, `AuthCacheSync` không render gì.
- **Chat stream có AbortController**; thiếu timeout và abort khi đóng panel (C10/C11), không phải thiếu controller.
- **Không có syntax highlighting** (highlight.js/Shiki) trong chat.
- **PDF parsing chạy trong worker** (`pdfjs.GlobalWorkerOptions.workerSrc`); chỉ phần paint canvas là main thread.

## 5. Cần đo thêm trên runtime

1. **Chrome Performance trên reader** (camera bật + gaze dot + chat streaming + PDF render, CPU throttle 4×): tách main-thread time theo React render / canvas encode / PDF paint / Markdown parse; xác nhận R01, R05, C02 và đo long task >50 ms.
2. **Đếm request bằng Playwright route interception:** `/layouts`, `/chat/access`, `/contents`, `/health` cho các kịch bản mở chat, cuộn chat, gửi 5 câu, đổi 10 slide. Mục tiêu: chat scroll = 0 `/layouts`; đổi slide = đúng 1 presentation + 1 layout.
3. **Memory:** heap snapshot sau 30 phút đọc (20 slide, 100 message), đo canvas backing store và số `PDFDocumentProxy` còn sống; kiểm tra S05/S06/S07.
4. **Giả lập lỗi WS:** close `1008`/`1013`, handshake treo, mất mạng 10 s; đếm số handshake trong 60 s và xác nhận camera được stop.
5. **Bundle:** `npm run analyze` trước/sau G9; so sánh HTML có skeleton hay bailout.
6. **Trade-off capture:** đo accuracy/bandwidth ở 320 px/q0.6 so với 480 px/q0.78 trên model thật (smoke) trước khi đổi mặc định.
7. **Range PDF:** xác nhận Range hoạt động end-to-end qua nginx + backend + R2 trước khi bỏ `disableRange/disableStream`.
8. **LCP/INP** `/student` và reader trên mạng 4G throttle, so sánh trước/sau L01/L03/L09.

## 6. Phụ lục — findings ngoài 3 luồng chính (teacher)

| Impact | File:Dòng | Khu vực | Nguyên nhân gốc rễ | Hướng tối ưu đề xuất (1 dòng) |
|---|---|---|---|---|
| **Med** | `X01` · `frontend/hooks/use-teacher.ts:23-38,48-62` | Teacher content | Hai poller 5 s (`courseTree`, `lessonSlidesAdmin`) có thể chạy đồng thời, mỗi refresh re-render editor và slide preview. | Một endpoint status nhẹ + backoff/ETag thay vì poll toàn payload. |
| **Med** | `X02` · `frontend/components/teacher/content-editor/lesson-editor/upload-helpers.ts:10-27` | Import slide | Poll 2 s tới 10 phút, không `AbortSignal`; rời trang vẫn tiếp tục và setState sau unmount. | Nhận `AbortSignal`, stop khi unmount, backoff 2→5→10 s. |
| **Med** | `X03` · `frontend/hooks/use-visualization.ts:32-48` | Replay | Poll 5 s khi có view pending/running, refetch cả payload replay. | Poll endpoint status nhẹ, dừng khi tab ẩn. |
| **Med** | `X04` · `frontend/components/teacher/visualization/replay/use-replay-player.ts:32-68` + `replay-stage.tsx:98` | Replay | `setTimeMsState` trong rAF ~60 Hz và `samples.findIndex` mỗi render (kể cả khi trail tắt) → O(#sample)/frame. | Giữ clock trong ref, chỉ update DOM dot/trail; precompute id→index và throttle 15–30 Hz. |
| **Med** | `X05` · `frontend/components/teacher/content-editor/slide-preview.tsx:34-62` | Slide grid | Map toàn bộ slide, mỗi slide một `LazyPdfPage` + observer; `visible` không bao giờ về false → 150 slide giữ 150 canvas. | Virtualize grid hoặc thumbnail ảnh + unmount off-screen. |
| **Med** | `X06` · `frontend/components/teacher/course-workspace.tsx:29-35,88` + `frontend/hooks/use-teacher.ts:16-21` | Teacher workspace | Tab mặc định `content` tải dynamic chunk → tree → slides → PDF; đồng thời fetch toàn bộ course list để tìm một course. | Thêm `GET /teacher/courses/{id}`, prefetch tree/slides song song, defer PDF thumbnail. |

## 7. Ghi chú phạm vi

- Phần này chỉ kết luận cho frontend. Không sửa code, không đổi schema/API.
- Số đo bundle lấy từ build production trong `frontend/.next` ngày 2026-11-20; số đo cache/asset lấy từ nginx local. Không dùng số liệu production.
- Các luồng teacher/replay chỉ nêu trong phụ lục vì không thuộc 3 luồng được yêu cầu; nếu cần audit sâu teacher analytics, tách phần riêng.
- Các đề xuất `High` ưu tiên theo thứ tự G1 → G4 → G5 → G7; các nhóm còn lại có thể làm song song theo file ownership.
