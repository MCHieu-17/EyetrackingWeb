# AGENTS.md — Eyetracking (EyeLearning)

> Nguồn sự thật: code hiện tại + `db/migrations/` + `scripts/`. Schema generation
> **13**, **24 bảng lõi**, không versioning nội dung. File này đã gộp `DB.md` cũ;
> không tạo lại `DB.md`, hãy cập nhật trực tiếp tại đây.

## 0. Bất biến — đọc trước khi sửa

- Không thêm bảng `*_versions`, `course_version_items`, `slide_documents`,
  `gaze_batches`, `aoi_sets`, `aoi_hits`, `analysis_runs`,
  `presentation_metrics`, `oauth_accounts`, `quiz_specs`.
- 24 bảng lõi **bao gồm** `app_metadata`; `schema_migrations` là bảng hạ tầng
  của migration runner, **không** tính vào 24. Các view `v_*` cũng không tính.
- Sửa nội dung đã publish áp dụng ngay. Quiz đã bắt đầu giữ đề trong
  `quiz_attempts.quiz_snapshot`; không có bản draft/published song song.
- `presentationId` là `content_views.id` — tên domain cho một lượt xem
  slide/quiz, không phải version.
- `gaze_samples.viewport_x/y` là toạ độ chuẩn hoá theo viewport tại thời điểm
  ghi và là nguồn duy nhất để map AOI. `slide_x/y`, `aoi_label`, metrics,
  `heatmap_grid`, `aoi_stats` đều là dữ liệu dẫn xuất, được phép tính lại.
- Mỗi gaze sample chỉ có **một** `aoi_label`: nhãn slide `SLIDE_<label>` /
  `SLIDE_NO_LABEL`, hoặc tên UI AOI / `UI_NO_LABEL`. Không lưu nhiều nhãn,
  không cộng container.
- Migration đã áp là bất biến: thêm file `009_...sql`, không sửa
  `001`–`005`. Không dùng `Base.metadata.create_all()` thay migration.
- Các biến model local (`DEVICE`, `UNIGAZE_MODEL`, `EMBEDDING_*`) phải đặt
  tường minh trong `.env`/`stack.env`; không thêm default trong code/compose.
- Không commit `.env`, `deploy/portainer/stack.env`, tunnel token, backup hay
  media. Không prune volume Docker.
- Bộ test hộp đen là lưới an toàn: không xoá test hoặc nới assertion để làm
  xanh CI; hành vi cố ý đổi thì cập nhật test trong cùng thay đổi.

## 1. Stack, service và cổng

| Thành phần | Công nghệ / vai trò |
|---|---|
| `frontend/` | Next.js 16 App Router, React 19, Tailwind 4, TanStack Query |
| `backend/` | FastAPI, Python 3.12.8, SQLAlchemy async, Pydantic 2; API + 3 worker |
| `services/gaze/` | FaceLandmarker + UniGaze đều là ONNX (onnxruntime, không torch/mediapipe ở runtime), WebSocket; mặc định cần GPU |
| `services/chatbot/` | FastAPI RAG: FTS + pgvector, embedding Qwen3-Embedding-0.6B trên CPU |
| `db/` | Baseline + migrations + role SQL; `db/migrate.sh` là runner duy nhất |
| `nginx/` | Reverse proxy local; production dùng `deploy/portainer/` |
| `scripts/` | Seed, reset có guard, backup, smoke, migration, publish image |

Cổng local (chỉ bind loopback):

| Cổng | Dịch vụ |
|---|---|
| `3000` | Website qua nginx, đồng thời `/api`, `/media`, `/gaze` |
| `8001` | Backend API / Swagger `/docs` |
| `8002` | Chatbot |
| `5435` | PostgreSQL 16 + pgvector |
| `6379` | Redis 7 |
| `6432` | PgBouncer (chỉ bật với profile `pgbouncer`) |

Gaze không publish cổng host vì có thể chạy nhiều replica; truy cập qua nginx
`/gaze/...` hoặc `docker compose exec gaze ...`.

Luồng request local:

```text
Browser → nginx :3000
  /api/teacher/*, /api/admin/* → backend :8001 (bỏ prefix /api)
  /api/*, /media/*             → backend :8001 (giữ prefix)
  /gaze/*                      → gaze :8000 (bỏ prefix /gaze)
  /*                           → frontend :3000
```

Next.js dev cũng rewrite `/api/teacher` và `/api/admin`; các `/api/*` khác giữ
nguyên. Backend route là nguồn sự thật, không đoán endpoint từ tài liệu.

## 2. Lệnh chạy và kiểm tra

Khởi động lần đầu:

```bash
cp .env.example .env          # điền secret, cấu hình SMTP/model
docker compose up -d --build  # service migrate chạy một lần rồi Exited (0)
./scripts/seed_dev.sh
./scripts/smoke.sh
```

`docker compose up -d --build` tự chạy migration. Khi sửa file SQL, phải rebuild
image migration (`docker compose build migrate`) — `test_migrations.sh` đã làm
việc này.

Kiểm tra code và test:

```bash
make check          # ruff + eslint + typecheck + compose config
make check-full     # thêm knip + frontend build
make test-fast      # backend + gaze + chatbot, mock model/LLM
make test-smoke     # model thật + chatbot RAG + Playwright trước merge
./scripts/test_migrations.sh
```

### 2.1 Bộ test đã có

Test hộp đen đã được triển khai; không dựng lại kế hoạch test. Chỉ bổ sung/sửa
case khi hành vi cố ý thay đổi.

| Khu vực | Vị trí | Số case | Lệnh |
|---|---|---|---|
| Backend | `backend/tests/fast/` | 84 fast | `./scripts/test_backend.sh` |
| Gaze | `services/gaze/tests/fast/` | 27 fast | `./scripts/test_gaze.sh fast` |
| Gaze smoke | `services/gaze/tests/smoke/` | 1 | `./scripts/test_gaze.sh smoke` |
| Chatbot | `services/chatbot/tests/fast/` | 31 fast | `./scripts/test_chatbot.sh fast` |
| Chatbot RAG smoke | `services/chatbot/tests/smoke/` | 1 | `./scripts/test_chatbot.sh smoke` |
| Frontend E2E | `frontend/e2e/` (Playwright) | 5 flow / 9 test | `./scripts/e2e.sh` |

- Backend chia theo file: `test_auth`, `test_courses_content`, `test_publish`,
  `test_visits_sessions`, `test_presentations`, `test_quiz`, `test_aoi`,
  `test_metrics`, `test_analytics`, `test_chat`, `test_maintenance`,
  `test_schema_contract`; helper ở `conftest.py` + `support/`.
- Gaze: `test_health_ready`, `test_session_api`, `test_calibration_regression`,
  `test_stream_ws`, `test_runtime_batch`; chatbot: `test_ingest_api`,
  `test_ingest_failures`, `test_query`, `test_embedding_queue`.
- `fast` mock model/LLM/VLM/embedding nhưng dùng PostgreSQL + Redis thật;
  `smoke` chạy model/LLM thật trên stack thật. Flow chat E2E chỉ bật khi
  `E2E_CHAT=1`.
- Backend/chatbot dùng database `eyetracking_test` và Redis DB 15; fixture
  truncate/flush trước mỗi test. DB test migrate bằng
  `docker compose run --rm migrate`, không `create_all()`.
- Test chạy trong image test riêng (`backend-test`, `chatbot-test`, `gaze-test`,
  compose profile `test`, Dockerfile target `test`) và mount `tests/` từ host.
  Image production không cài pytest. `test_backend.sh` / `test_chatbot.sh` tạo
  lại DB test trước khi chạy.
- Mock nằm ở biên: `respx` cho chatbot/LMS, fake VLM/embedding/LLM, fake gaze
  runtime. Fixture được seed bằng SQL; assertion cuối vẫn qua API/DB như người
  dùng thật.
- Calibration gaze kiểm tra Linear Regression thật qua HTTP/WS; smoke dùng
  `services/gaze/tests/fixtures/face_sample.jpg` (CC0, nguồn trong
  `fixtures/README.md`).
- E2E seed bằng `scripts/seed_e2e.py`, ghi `frontend/e2e/.fixtures.json`
  (gitignored) và xoá course prefix `E2E Seed` / `E2E Draft` trước khi chạy.
- Sửa hành vi có chủ đích thì cập nhật test trong cùng thay đổi; không xoá test
  để làm xanh CI.

### 2.2 Seed dev, reset và backup

Seed dev (mật khẩu `Password123!`): `admin@school.edu.vn` (admin),
`teacher@school.edu.vn` (teacher), `student@school.edu.vn` (student). Script
không ghi đè mật khẩu đã tồn tại.

Reset/backup:

```bash
./scripts/backup.sh
./scripts/reset_db.sh                  # preview, không đổi gì
./scripts/reset_db.sh --apply --database eyetracking \
  --confirm-reset eyetracking --seed-dev
./scripts/reset_gaze_data.sh --all     # preview; thêm --apply --confirm-reset-gaze
```

`reset_db.sh` chỉ xoá database đích sau khi guard khớp; không dùng
`docker compose down -v` để reset (mất DB, media, weights, Redis). `reset_gaze_data.sh`
chỉ xoá lịch sử gaze (`course_visits` cascade) và job analyze đang chờ, giữ
nội dung khoá học/AOI/người dùng.

### 2.3 Áp dụng biến môi trường

Sau khi sửa `.env`, dùng `docker compose up -d --force-recreate <service>`;
`docker compose restart` không áp dụng biến môi trường mới.

### 2.4 Benchmark baseline

Harness nằm trong `benchmarks/`, chạy trên stack cô lập
`eyelearning-bench` (port nginx `3100`, backend `8101`, chatbot `8102`,
Postgres `5436`, Redis `6380`; DB `eyetracking_bench`). Không đo trên stack
dev/production và không dùng `next dev`.

```bash
./benchmarks/preflight.sh
./benchmarks/run_all.sh --quick --scale tiny     # smoke harness
./benchmarks/run_all.sh --scale baseline         # baseline đầy đủ
./benchmarks/run_all.sh --only backend --quick   # một nhóm
```

- Kết quả JSON/Markdown nằm trong `benchmarks/baseline/<run-id>/`; so sánh
  bằng `benchmarks/report/compare.py`.
- Gaze có harness riêng trong `benchmarks/gaze/`: `standalone.sh` (một container,
  không cần stack bench), `run.sh` (nhóm gaze của `run_all.sh`), và `tools/`
  (`eval_offline.py`, `compare_capture.py`, `compare_precision.py`, `bench.py`).
  Script đo **không** nằm trong image runtime; mount `benchmarks/` vào `/bench`
  rồi chạy `python /bench/gaze/tools/<script>.py` (script tự thêm `/app` vào
  `sys.path`).
- Ảnh mặt cho đo độ chính xác ở `benchmarks/gaze/testdata/` là dữ liệu khuôn
  mặt thật, **gitignored**; kết quả JSON thô của nghiên cứu gốc ở
  `benchmarks/gaze/research-results/`. Báo cáo nghiên cứu (kiến trúc, accuracy,
  benchmark) nằm ở `docs/gaze/`.
- Stack benchmark dùng chung weights gaze/chatbot với dev qua external volume,
  nhưng DB/media/Redis riêng. Không seed vào DB không kết thúc bằng `_bench`.
- Đo capacity trực tiếp backend `:8101`; nginx có `api_rl` 20 r/s/IP nên chỉ
  dùng để đo overhead/user-facing.
- Chatbot hiện là pipeline tuyến tính, không LangGraph; ingest không chunk
  text (mỗi slide là một transcript/embedding). Gaze calibration dùng numpy
  `lstsq`, không sklearn.
- Benchmark không thay thế test hộp đen; sửa hành vi vẫn phải cập nhật test.

## 3. Bố cục code và ranh giới

- `backend/app/api/routes/`: transport + validation; giữ mỏng.
- `backend/app/services/`: business logic, access policy, worker, analytics.
- `backend/app/models/`: ánh xạ 24 bảng; `backend/app/schemas/`: Pydantic,
  API dùng camelCase qua `CamelModel`.
- `backend/app/main.py`: đăng ký router và **fail-fast** nếu
  `app_metadata.schema_generation != '13'`.
- `backend/Dockerfile` có 3 target: `api` (backend/worker/embedding-worker),
  `content-worker` (thêm LibreOffice + fonts) và `test` (thêm dev deps cho
  pytest). Worker content không nằm trong image API; target `test` không dùng
  cho production.
- `services/gaze/` chỉ xử lý calibration/WebSocket/frame; backend mới ghi DB.
- `services/chatbot/` chỉ đọc view outline + đọc/ghi cột index trên `slides`.
- `frontend/` gọi API qua `lib/api/`, không truy cập DB; PDF render bằng PDF.js.
- `benchmarks/` là harness đo hiệu năng; không import vào app production, không
  thay đổi schema/API. Artifact nằm dưới `benchmarks/baseline/` và không chứa
  secret (token nằm trong `.runtime/` đã gitignore). `benchmarks/gaze/tools/`
  chỉ đọc code `app/*` của gaze, không bị import ngược lại.
- `docs/gaze/` giữ báo cáo nghiên cứu gaze (kiến trúc, accuracy, benchmark);
  không tạo lại pipeline torch hay `gaze_research/` trong repo này.
- `services/gaze/scripts/` chỉ còn script cần trong image (export ONNX, tải
  weights); script đo/thuộc tính năng phụ thuộc `benchmarks/`.

## 4. Mô hình dữ liệu

### 4.1 ERD rút gọn

```text
courses
  └── course_modules
        └── lessons
              ├── slides → aois
              └── quiz_attempts

enrollments
  └── course_visits
        └── learning_sessions
              └── content_views
                    ├── view_layouts
                    └── gaze_samples

users → auth_sessions, profiles, gaze_calibrations, chat_sessions
chat_sessions → chat_messages
```

### 4.2 24 bảng lõi

| # | Nhóm | Bảng | Cột / ràng buộc đáng nhớ |
|---:|---|---|---|
| 1 | Danh tính | `users` | `role` admin/teacher/student; `status`; `email` unique lower; `password_hash` nullable cho OTP; `email_verified_at` |
| 2 | | `auth_sessions` | Chỉ lưu `refresh_token_hash`; `expires_at`, `revoked_at` |
| 3 | | `email_otps` | `code_hash` HMAC-SHA256; `consumed_at`/`invalidated_at`; partial unique một challenge active/email |
| 4 | | `student_profiles` | 1:1 `user_id`, `student_code` unique |
| 5 | | `teacher_profiles` | 1:1 `user_id`, `teacher_code` unique |
| 6 | Khóa học | `courses` | `owner_id`, `created_by`, status draft/published/archived, `show_gaze_dot`, `show_camera_preview`, `require_calibration` |
| 7 | | `course_teachers` | PK `(course_id, teacher_id)`; chỉ được xem, không sở hữu |
| 8 | | `enrollments` | Unique `(course_id, student_id)`; status active/completed/dropped |
| 9 | | `course_visits` | “Ca học”; status active/ended/expired; `visit_key` unique theo enrollment; `last_seen_at` |
| 10 | | `media_assets` | local/r2; unique `(course_id, sha256)`; state staging/ready/failed/deleted |
| 11 | Nội dung | `course_modules` | Unique `(course_id, position)` |
| 12 | | `lessons` | `module_id`, kind lesson/quiz, unique `(module_id, position)`, `pdf_asset_id`, `quiz_config` JSONB |
| 13 | | `slides` | Unique `(lesson_id, position)`; `page_number`; `transcript`; `embedding vector(1024)`; FTS generated; `index_status` |
| 14 | Job | `background_jobs` | `lesson_id` NOT NULL; kind import_slides/index_slides/analyze_lesson; status queued/processing/ready/failed/cancelled |
| 15 | Quiz | `quiz_attempts` | Unique `(enrollment, lesson, attempt_no)`; partial unique một `in_progress`; snapshot/answers/grading JSONB |
| 16 | Gaze/AOI | `gaze_calibrations` | Model UBJ + hash + viewport/DPR + `num_points`; current = row mới nhất theo user/device |
| 17 | | `learning_sessions` | `enrollment_id`, `lesson_id`, `course_visit_id`, `quiz_attempt_id`, calibration; viewport hiện tại + calibration; status; `expires_at` |
| 18 | | `content_views` | `session_id`, `slide_id` nullable (quiz), surface lesson/quiz, `sequence_no` unique/session, metrics + `heatmap_grid` + `aoi_stats` |
| 19 | | `view_layouts` | `layout_no` unique/view; `slide_rect` + `elements` JSONB; chỉ hệ viewport hiện tại |
| 20 | | `gaze_samples` | `BIGSERIAL`; unique `(content_view, batch, sequence)`; viewport canonical, slide derived, một `aoi_label` |
| 21 | | `aois` | Đúng một trong `slide_id`/`ui_schema`; `code`, `name`, `label`, `parent_id`, `geometry`, `is_container`, `kind` |
| 22 | Chat | `chat_sessions` | student/course/lesson/quiz; `context_key`, `archived_at` |
| 23 | | `chat_messages` | role student/assistant; `content`, `citations` JSONB, `intent` |
| 24 | Metadata | `app_metadata` | `schema_generation='13'`, `db_instance_id` |

`background_jobs`, `content_views`, `gaze_samples` là các bảng dễ viết sai
nhất khi thêm tính năng; đọc migration tương ứng trước khi sửa query.

### 4.3 Quy ước schema

- PK UUID `gen_random_uuid()`, riêng `gaze_samples.id` là `BIGSERIAL`.
- Timestamp `TIMESTAMPTZ` UTC. Không hardcode pixel; mọi toạ độ gaze/AOI đã
  chuẩn hoá.
- FK cascade là cơ chế xoá dữ liệu liên quan chính; file media local/R2 được
  dọn **sau** transaction DB theo prefix/object key.
- JSONB chỉ dùng cho dữ liệu lồng nhau có kiểm soát hoặc derived: `quiz_config`,
  `quiz_snapshot`, `answers`, `grading`, `heatmap_grid`, `aoi_stats`,
  `slide_rect`, `elements`, `aois.geometry`, `quality_flags`, `citations`,
  `payload`.
- Unique/partial index quan trọng: `users(lower(email))`;
  `email_otps(email) WHERE active`; `course_visits(enrollment_id, visit_key)
  WHERE visit_key IS NOT NULL`; `quiz_attempts(enrollment, lesson) WHERE
  status='in_progress'`; `aois(slide_id, code)`, `aois(ui_schema, code)`,
  `aois(slide_id, label)`.
- `schema_migrations` lưu filename + checksum SHA-256; không sửa file đã áp.
- `gaze_samples.event_time` dùng BRIN `idx_gaze_samples_event_time_brin`
  (append-only/retention); `idx_gaze_samples_view_time` phục vụ analysis,
  replay và export theo từng lượt xem.
- `slides.embedding` là `vector(1024)`; `EMBEDDING_DIM` hiện phải là `1024`.
  Đổi model/chiều embedding cần migration + reindex toàn bộ slide, không chỉ
  đổi biến môi trường.
- `aois.label` do giáo viên đặt, regex app-level `^AOI_[A-Z0-9_]{1,60}$`,
  unique trong slide; UI/container/no_label để NULL. Nhãn gaze có tiền tố
  `SLIDE_`; UI dùng `aois.name`.
- `content_views.analysis_version` hiện là `gaze-metrics-v8`; heatmap chỉ dùng
  view `ready` + đúng version + grid đủ 24×24, còn tổng hợp đánh dấu stale nếu
  sai version hoặc thiếu `aoi_stats` khi đã có gaze. View cũ có thể phân tích
  lại, không cần xoá gaze thô.

### 4.4 Cascade xoá

| Xoá | Dữ liệu mất |
|---|---|
| `courses` | modules, lessons, slides, aois, media, enrollments, visits, sessions, views, layouts, samples, quiz attempts, chats, jobs |
| `course_modules` | lessons và toàn bộ dữ liệu con của lessons |
| `lessons` | slides, quiz attempts, learning sessions, views, gaze, chats, jobs |
| `slides` | aois, content views (kéo theo layouts, gaze samples) |
| `enrollments` | course visits, learning sessions/views/gaze, quiz attempts |
| `users` | profiles, enrollments, auth sessions, calibrations, chat; courses do user sở hữu cũng cascade, còn `courses.created_by` là RESTRICT |
| `background_jobs` | không cascade ngược; job thuộc lesson và bị xoá khi lesson bị xoá |

Không có trigger bất biến hay cờ `app.allow_course_delete`. Kiểm tra cascade
thủ công bằng SQL khi sửa FK; test cascade nằm trong
`backend/tests/fast/test_courses_content.py` và `test_schema_contract.py`.

## 5. Gaze → AOI → metrics

### 5.1 Pipeline

```text
viewport_x/y (normalized, viewport lúc ghi)
  → trừ slide_rect.left/top, chia width/height
  → slide_x/y

slide_x/y trong [0,1]
  → chọn MỘT leaf slide đang active:
    custom > text > table > image > drawing > system;
    cùng hạng thì diện tích nhỏ hơn, rồi code
  → SLIDE_<aois.label>; không match → SLIDE_NO_LABEL

ngoài slide / quiz / thiếu layout
  → chọn MỘT UI AOI: custom trước, rồi diện tích nhỏ hơn, rồi code
  → aois.name; không match → UI_NO_LABEL

toàn bộ sample của content_view
  → gaze_count, on_slide_gaze_count
  → tracked_duration_ms = tổng gap sample hợp lệ
  → fixation_count
  → heatmap_grid 24×24 row-major, grid[y][x]
  → aoi_stats = {label: {ms, samples}}
```

- Container, `is_active=false`, code `no_label` bị bỏ qua khi match.
- Thiếu layout hoặc `slide_rect` rỗng: không identity map; `slide_x/y = NULL`,
  `quality_flags.layout_missing=true`, rơi về nhãn UI.
- `gaze_samples.aoi_label` có thể NULL với sample lỗi/không map được; sample
  `status='ok'` bắt buộc có `viewport_x/y`, status khác bắt buộc NULL.
- `view_layouts` chỉ lưu hệ toạ độ viewport hiện tại. Payload
  `coordinateSpace='original-v1'` bị từ chối `409`; không tái thêm
  `original_viewport_x/y`, `coordinate_space`, `visible_rect`.

### 5.2 Hai loại thời lượng — đừng nhầm

- `content_views.tracked_duration_ms`: worker cộng các gap giữa sample hợp lệ,
  chỉ khi `0 <= gap <= max(250, ceil(3000 / GAZE_FPS))` ms. Đây là thời lượng
  theo sample, không phải thời gian treo tab.
- `dwell_ms`: tính khi đọc, theo wall time:
  `COALESCE(view.ended_at, session.ended_at, visit.ended_at, now()) - started_at`.
  `CONTENT_VIEW_MIN_DWELL_MS` (mặc định 1000) chỉ phân loại `counted` và bộ
  lọc “Chỉ lượt >= ngưỡng”; mặc định Replay/Tổng hợp vẫn trả mọi lượt, kể cả
  0 sample hoặc thiếu layout.
- `heatmap_grid` chỉ cộng sample nằm trong slide; `aoi_stats.ms` cộng gap cho
  nhãn của sample, `samples` đếm sample `ok` có nhãn.
- Sửa/xoá AOI không xoá gaze thô: enqueue phân tích lại để tính `slide_x/y`,
  `aoi_label`, metrics và `aoi_stats` mới.

### 5.3 AOI UI và replay

- `aois` UI dùng `ui_schema='reader-v1'`; `geometry` là `selector` hoặc
  `anchor` + rect (container có thể rỗng; dữ liệu cũ có thể chứa rect trực
  tiếp). `backend/app/services/aoi_regions.py` là nguồn duy nhất quy đổi
  geometry UI, dùng chung bởi worker và replay.
- `view_layouts.elements` là snapshot các phần tử `[data-aoi]`, gồm rect
  normalized; `elements` có thể có nhiều instance cùng code.
- Replay dùng đúng implementation đó để vùng AOI sáng khớp nhãn đã lưu.

### 5.4 Client gaze flow

1. WebSocket tới gaze service; frame được throttle theo `GAZE_FPS`.
2. Frontend quy đổi toạ độ calibration → viewport hiện tại, gửi batch
   `POST /api/learning-sessions/{id}/gaze-batches`.
3. Backend ghi trực tiếp `gaze_samples`, unique
   `(content_view_id, client_batch_id, sequence)`; duplicate bị bỏ qua và trả
   `duplicate > 0`.
4. Đóng session enqueue `analyze_lesson`; worker phân tích theo content view.
5. Display guard phát hiện zoom/fullscreen và tạm dừng ghi; resize cửa sổ tạm
   dừng để snapshot layout mới. Trình duyệt không chặn tuyệt đối F11/page
   zoom — guard là best-effort, không được giả định đã chặn.

## 6. Luồng giáo viên và học viên

### 6.1 Giáo viên

1. Tạo khoá `draft`; tạo chương `course_modules`, bài `lessons` với
   `module_id` + `position`.
2. Upload PDF/PPTX/PPT/ODP: API lưu staging, trả `202 {jobId}`, tạo
   `background_jobs(kind='import_slides')`; content-worker convert PDF, thay
   toàn bộ slides, set `index_status='pending'`, enqueue `index_slides`.
3. Replace PDF của bài = xoá slides cũ + cascade AOI/view/gaze của các slide
   đó; không cố giữ dữ liệu gaze cũ.
4. Quiz nằm trong `lessons.quiz_config`; `quiz_attempts` giữ snapshot.
5. AOI vẽ tay trong tab “Vùng phân tích”, lưu trực tiếp `aois`; lưu AOI sẽ
   enqueue phân tích lại các view của bài.
6. Publish validate: có chương/bài; bài giảng có slide; mọi slide
   `index_status='ready'`; media `ready`; quiz có câu hỏi/đáp án/điểm hợp lệ.
   Sau đó chỉ đổi `courses.status='published'` và `published_at`.
7. `PATCH /teacher/lessons/{id}/quiz` với `status='published'` cũng gọi
   publish course, nên có thể thất bại nếu phần còn lại chưa đủ điều kiện.

### 6.2 Học viên

1. Đăng nhập OTP → enroll → nếu `require_calibration` thì calibration 25 điểm.
2. Mở khoá: `POST /api/course-visits`; mỗi lần vào khoá là một ca. `visit_key`
   idempotent theo `(enrollment, visit_key)`. Ca idle quá 30 phút bị maintenance
   đánh `expired`.
3. Mở bài: `POST /api/learning-sessions`; session thuộc ca, TTL 12 giờ. Cùng
   enrollment + lesson + context thì trả session đang mở; đổi calibration/
   viewport thì session cũ bị `aborted`.
4. Mỗi slide/quiz: `POST /api/learning-sessions/{id}/presentations` với
   `clientPresentationId`. Cùng UUID + cùng context là idempotent; UUID mới
   luôn tạo lượt mới kể cả quay lại slide cũ. Server khoá session và cấp
   `sequence_no = max + 1`, không dùng bộ đếm client.
5. `enteredAt` bị kẹp trong `[now - 5 phút, now]`; request đến trễ hơn lượt
   mới nhất quá 250ms bị `409 stale_presentation`.
6. Resize/mở chat/đổi layout: `POST /api/presentations/{id}/layouts`; mỗi
   `layout_no` unique trong presentation.
7. Đóng session: `PATCH /api/learning-sessions/{id}`, đóng mọi view mở, enqueue
   `analyze_lesson`. Đóng ca: `PATCH /api/course-visits/{id}`.
8. Tab Trực quan hoá hiển thị **tất cả** lượt xem; `includeShort=true` mặc
   định, chỉ bật `false` khi người dùng chọn lọc “Chỉ lượt >= ngưỡng”. FE mặc
   định gửi `from` = hôm nay-90 ngày (hiện trong ô ngày, xoá được để xem
   all-time); backend vẫn nhận `from`/`to` rỗng nghĩa là toàn bộ lịch sử.

## 7. API contract và quy ước

- API dùng camelCase; DB dùng snake_case. `CamelModel` đặt
  `alias_generator=to_camel`, `populate_by_name=True`.
- ID thống nhất: `slideId=slides.id`, `lessonId=lessons.id`,
  `presentationId=content_views.id`, `layoutId=view_layouts.id`.
- Backend route teacher/admin không có prefix `/api`; browser gọi
  `/api/teacher/...` hoặc `/api/admin/...` và được rewrite. Các route `/api/*`
  khác giữ nguyên prefix.
- Route module là nguồn sự thật; danh sách dưới đây chỉ là các endpoint dễ
  quên:

| Endpoint | Ý nghĩa |
|---|---|
| `POST /api/auth/otp/request`, `/otp/verify` | OTP sinh viên |
| `POST /api/auth/login` | Giáo viên/admin đăng nhập mật khẩu |
| `GET /api/config` | `gazeFps`, `maxUploadBytes`, `maxSlidePages`, không cache |
| `GET /api/health` | Alias công khai của `/health` |
| `POST /api/course-visits`, `GET /api/course-visits/active`, `PATCH /api/course-visits/{id}` | Ca học |
| `POST /api/learning-sessions`, `PATCH /api/learning-sessions/{id}` | Phiên học |
| `POST /api/learning-sessions/{id}/presentations` | Tạo content view |
| `POST /api/presentations/{id}/layouts` | Snapshot layout |
| `POST /api/learning-sessions/{id}/gaze-batches` | Ghi gaze batch |
| `GET /api/aois?slideId=...` | AOI hiện hành của slide |
| `GET /api/lessons/{id}/quiz`, `PATCH /teacher/lessons/{id}/quiz` | Quiz |
| `GET /teacher/courses/{courseId}/visits` | Tất cả ca của khoá |
| `GET /teacher/visits/{visitId}/gaze` | Gaze/AOI của ca |
| `GET /teacher/visits/{visitId}/replay` | Layout + AOI + thống kê replay |
| `GET /teacher/visits/{visitId}/samples?contentViewId=...` | Sample keyset |
| `POST /teacher/courses/{courseId}/analytics/aoi-summary` | Tổng hợp AOI |
| `POST /teacher/courses/{courseId}/analytics/heatmap` | Heatmap 24×24 |
| `GET /teacher/visits/{visitId}/export`, `/teacher/lessons/{id}/export` | JSONL phẳng |

`POST /api/auth/otp/request` trả `challengeId` (UUID của row OTP); mã không bao
giờ lưu/log ở production. OTP mặc định 6 số, TTL 15 phút, tối đa 5 lần nhập,
resend 60 giây; email khớp domain + pattern cấu hình.

## 8. Chatbot / RAG

- Index nằm trên `slides` (`transcript`, `embedding`, `content_tsv`,
  `index_status`, `index_error`); worker gọi chatbot `/ingest/slides` theo batch.
- Backend enqueue `index_slides` khi slide mới; publish chặn nếu còn slide
  `index_status != 'ready'`.
- Retrieval lọc theo `course_id`; citation mới dùng
  `courseId/lessonId/slideId/assetId/pageNumber` (response có alias cũ cho
  frontend).
- Chatbot chỉ có role `chatbot_reader`: SELECT 3 view outline + SELECT/UPDATE
  cột index trên `slides`; không đọc users, enrollments, quiz, chat.
- Backend lưu `chat_sessions/chat_messages`; chatbot không được đọc lịch sử
  của user khác.
- Gọi LLM/VLM qua endpoint OpenAI-compatible bằng nhóm biến `LLM_*`/`VLM_*`;
  không thêm key `NEU_*`, không hardcode endpoint/model của nhà cung cấp.

## 9. Auth và OTP

- Sinh viên: email trường + OTP qua SMTP. Không cần Microsoft Entra/Azure;
  không dùng `MICROSOFT_CLIENT_ID/SECRET/TENANT_ID`.
- OTP lưu `HMAC-SHA256(email:code)`; một challenge active/email; maintenance
  xoá row hết hạn quá 1 ngày.
- Email hợp lệ mặc định: local part `^\d{8}$`, domain `st.neu.edu.vn`
  (`OTP_ALLOWED_DOMAINS` có thể nhận nhiều domain).
- Giáo viên/admin dùng mật khẩu; seed dev dùng `Password123!`.
- SMTP chưa cấu hình → API trả 503; dev có thể bật `DEBUG=true` +
  `OTP_DEV_ECHO=true` để log mã. Không bật ở production.
- Local HTTP phải đặt `COOKIE_SECURE=false`; nếu không cookie auth không được
  lưu. Production dùng HTTPS và cookie secure.
- Gmail cá nhân gửi tới `st.neu.edu.vn` có thể vào Spam/Quarantine lần đầu;
  lỗi `550 5.4.1 Recipient address rejected` là địa chỉ không tồn tại, không
  phải lỗi cấu hình SMTP.

## 10. Migration, retention và role DB

- Baseline `001_baseline.sql` là generation 12 (24 bảng); `002_email_otp.sql`
  nâng generation 13; `003_aoi_single_label.sql` bỏ `aoi_codes` /
  `aoi_suggestions`; `004_content_view_aoi_stats.sql` thêm `aoi_stats`;
  `005_current_viewport_only.sql` bỏ hệ toạ độ cũ;
  `006_gaze_sample_indexes.sql` thay btree `event_time` bằng BRIN;
  `007_reset_gaze_calibrations.sql` xoá calibration cũ khi đổi pipeline gaze
  (không đổi schema); `008_course_camera_preview.sql` thêm
  `courses.show_camera_preview` (mặc định `false`, không đổi generation).
- Thay đổi schema mới phải là `009_...sql`; không sửa migration đã áp.
  `db/migrate.sh` giữ advisory lock, ghi checksum, fail nếu file đã áp bị đổi
  hoặc DB có bảng public mà chưa có `schema_migrations`.
- Không chạy `psql -f` từng file migration; dùng `docker compose run --rm migrate`
  hoặc service `migrate`.
- Backend fail-fast nếu `app_metadata.schema_generation != '13'`. DB cũ không
  migrate tại chỗ nếu chưa có lịch sử migration: backup rồi reset có guard.
- Role `chatbot_reader` và `admin_reader` do `db/migrate.sh` tạo/cập nhật.
  `admin_reader` không đọc `auth_sessions`, `email_otps`; `users` chỉ đọc cột
  an toàn (không `password_hash`). Grant lại khi thêm bảng bằng cách chạy lại
  `docker compose run --rm migrate` (idempotent).
- Retention: gaze mặc định 180 ngày (`GAZE_RETENTION_DAYS`); maintenance xoá
  auth session hết hạn, expire learning session/visit, xoá OTP hết hạn quá 1
  ngày và gaze cũ. `gaze_samples` không còn partition tháng.
- `./scripts/maintenance.sh` chạy maintenance; `./scripts/test_migrations.sh`
  kiểm tra checksum, idempotent, generation 13 và đúng 24 bảng.

## 11. Cấu hình, deploy và vận hành

- `.env` ở gốc repo là nguồn env duy nhất cho local; frontend Docker build
  nhận build args, không đọc `.env` trong context frontend.
- Biến bắt buộc tối thiểu: `POSTGRES_*`, `DATABASE_URL_DOCKER`, `JWT_SECRET`,
  `CORS_ORIGINS`; model local `DEVICE`, `UNIGAZE_MODEL`, `EMBEDDING_*`.
- `GAZE_FPS` (1..60, mặc định 15) là nguồn duy nhất cho tần số gaze: backend
  trả `/api/config`, gaze throttle `1000/FPS × 0.85`, worker dùng gap
  `max(250, ceil(3000/FPS))`. Đổi FPS cần restart backend + gaze; frontend đọc
  runtime nên không rebuild.
- `CONTENT_VIEW_MIN_DWELL_MS` chỉ ảnh hưởng phân loại/lọc; đổi cần recreate
  backend.
- `DB_PREPARED_STATEMENT_CACHE_SIZE` mặc định `64` khi nối trực tiếp
  PostgreSQL; profile `pgbouncer` (transaction pooling) phải đặt `0` trong
  `.env`.
- Local: `docker compose up -d --build`; `migrate` exit 0 là bình thường.
  `docker compose down -v` xoá DB/media/weights/Redis — chỉ dùng khi thật sự
  muốn reset sạch.
- Production: GitHub Actions build 8 image (backend, content-worker, chatbot,
  gaze, gaze-export, frontend, nginx, migrations) → GHCR; Portainer chỉ pull
  `deploy/portainer/docker-compose.yml`, không build trên server. `cloudflared`
  nằm trong stack, trỏ `http://nginx:80`.
- Nginx production phải giữ `real_ip_header CF-Connecting-IP` và forward
  `X-Forwarded-Proto`; nếu không rate limit/OTP sẽ tính chung IP cloudflared.
- Không commit `deploy/portainer/stack.env`, tunnel token, backup. Hướng dẫn
  đầy đủ: `deploy/portainer/README.md`.
- Redis là service compose bình thường nhưng backend chịu được thiếu Redis ở
  mức cache/rate-limit tùy tính năng; không coi Redis là nguồn sự thật.

## 12. Quy tắc Refactor & Tối ưu

- Giữ nguyên hành vi chức năng hiện tại: cùng input → cùng output, status code,
  side effect và thứ tự ghi DB. Refactor không kèm đổi feature.
- Nếu buộc phải đổi API contract (field, kiểu, endpoint, status), báo trước và
  cập nhật frontend, schema Pydantic và tài liệu trong cùng thay đổi.
- Không tự ý cài thêm thư viện ngoài khi chưa được duyệt; ưu tiên thư viện đã
  có trong `package.json`, `requirements*.txt` và image hiện tại.
- Chỉ sửa file trong phạm vi thư mục được chỉ định ở từng task; không lan sang
  module khác, không dọn dẹp ngoài phạm vi, không đổi format cả file.
- Luôn giữ code ngắn gọn, ưu tiên chuẩn của stack: FastAPI (dependency
  injection, Pydantic, async), Next.js (App Router, ranh giới server/client),
  Postgres (SQL set-based, index đúng), Redis (key/TTL rõ ràng), PyTorch
  (`eval`/`no_grad`, đúng `DEVICE`) và LangGraph (StateGraph/node rõ ràng) khi
  luồng agent dùng tới.

## 13. Checklist cho agent trước khi kết thúc

- Đọc migration/model/route liên quan; ưu tiên code hơn README nếu lệch.
- Nếu sửa schema: thêm `009_...sql`, cập nhật model/schema/API, chạy
  `./scripts/test_migrations.sh` và `./scripts/test_backend.sh`.
- Nếu sửa cascade/FK/metrics/AOI: chạy `./scripts/test_backend.sh`; test metrics
  nằm trong `backend/tests/fast/test_metrics.py` và `test_analytics.py`, cascade
  trong `test_courses_content.py` và `test_schema_contract.py`.
- Nếu sửa gaze service/WS/layout: chạy `./scripts/test_backend.sh` và
  `./scripts/test_gaze.sh fast`; chạy `./scripts/test_gaze.sh smoke` nếu sửa
  model/preprocess; kiểm tra thêm `aoi_regions.py` + replay.
- Nếu sửa chatbot ingest/retrieval/query/SSE: chạy
  `./scripts/test_chatbot.sh fast`; chạy `./scripts/test_chatbot.sh smoke` khi
  sửa luồng ingest hoặc LLM.
- Nếu sửa frontend API: giữ camelCase và rewrite `/api/teacher|admin`; cập nhật
  query key/hook và chạy `./scripts/e2e.sh` nếu đổi luồng người dùng
  (`E2E_CHAT=1 ./scripts/e2e.sh` nếu đổi chat).
- Nếu sửa luồng hiệu năng backend/DB/gaze/chatbot: chạy nhóm benchmark liên
  quan (`./benchmarks/run_all.sh --only backend --quick`, tương tự `gaze` /
  `chatbot`) trước khi kết luận tối ưu; baseline đầy đủ chỉ chạy khi có
  stack/GPU/LLM.
- Nếu sửa env/compose: cập nhật `.env.example` và `deploy/portainer/stack.env.example`;
  không thêm default cho model local.
- Nếu sửa hành vi người dùng: cập nhật `README.md`/`backend/README.md` và mục
  tương ứng trong file này; không tạo lại `DB.md`.
- Trước khi dừng: chạy `make check` và `make test-fast`; chạy `make test-smoke`
  nếu có stack/GPU/LLM. Ghi rõ phần chưa kiểm tra được vì thiếu môi trường.
