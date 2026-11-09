# Backend — GazeEdu (EyeLearning)

FastAPI backend cho hệ thống học tập theo dõi hành vi mắt (eye-tracking).

## Kiến trúc

```
backend/app/
├── main.py              # FastAPI app, CORS, routers, schema guard
├── content_worker.py    # worker chuyển đổi slide upload -> PDF + slide rows
├── worker.py            # worker tính analysis runs
├── core/
│   ├── config.py        # Settings (pydantic-settings, đọc .env gốc repo)
│   ├── security.py      # bcrypt + JWT (access/refresh)
│   ├── csrf.py          # CSRF double-submit cho cookie auth
│   ├── ratelimit.py     # rate limit Redis/in-memory
│   └── helpers.py       # gradient/color palette, relative time tiếng Việt
├── db/
│   ├── base.py          # SQLAlchemy Base
│   ├── session.py       # async engine + session (asyncpg)
│   └── redis.py         # Redis client
├── models/              # SQLAlchemy models ánh xạ db/migrations/*.sql
├── schemas/             # Pydantic v2 — camelCase, khớp frontend
├── crud/                # data access
├── services/            # content, media, embedding, analysis, metrics, chat
└── api/
    ├── deps.py          # get_current_user, require_roles (RBAC)
    ├── access.py        # helper course/module/lesson
    └── routes/          # auth, users, courses, lessons, media, chat, gaze, ...
```

## Chạy

### Cách 1: Docker Compose (khuyến nghị)

```bash
docker compose up -d --build
```

### Cách 2: Chạy trực tiếp (dev)

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m uvicorn app.main:app --reload --port 8001
```

Cần PostgreSQL + Redis đang chạy (có thể dùng service trong compose).

### API và worker dùng chung image

`backend/Dockerfile` có 2 target:

| Target | Dùng cho | Nội dung |
|---|---|---|
| `api` | service `backend` + `worker` | FastAPI + `app.worker` (analysis), **không** LibreOffice |
| `content-worker` | service `content-worker` | thêm LibreOffice + fonts để chuyển PPTX/PPT/ODP → PDF |

API không cài LibreOffice nên image nhẹ và khởi động nhanh; chỉ content-worker
có `soffice`. Cả hai chạy bằng user `appuser` (không phải root).

## Cấu hình (env — một file duy nhất ở gốc repo)

Backend đọc mọi biến từ **`.env` ở gốc repo** (`backend/app/core/config.py` trỏ
thẳng tới `ROOT_ENV_FILE`). Không còn giá trị mẫu nhúng trong code.

| Biến | Bắt buộc | Ý nghĩa |
|---|---|---|
| `DATABASE_URL` | Chỉ host | Chuỗi kết nối PG (asyncpg) khi chạy backend ngoài container (`localhost:5435`) |
| `DATABASE_URL_DOCKER` | Có (compose) | Chuỗi kết nối DB nội bộ cho container backend |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Có (compose) | Tạo DB của service `postgres` |
| `REDIS_URL` | Không | Redis khi chạy host (`redis://localhost:6379/0`); trống = fallback in-memory |
| `JWT_SECRET` | Có | Chuỗi random dài; không dùng giá trị mẫu |
| `CORS_ORIGINS` | Có | Phân tách bằng dấu phẩy |
| `AI_HTTP_URL` | Có (compose) | Gaze service; compose tự set `http://gaze:8000` |
| `CHATBOT_URL` | Chỉ host | Chatbot service khi backend chạy host (`http://localhost:8002`) |
| `CHATBOT_INTERNAL_TOKEN` | Có (nếu dùng chat) | Token nội bộ backend → chatbot |
| `CHATBOT_TIMEOUT_SECONDS` | Không | Timeout gọi chatbot (mặc định 120) |
| `CHATBOT_INGEST_TIMEOUT_SECONDS` | Không | Timeout ingest slide (mặc định 600) |
| `CHATBOT_INGEST_ATTEMPTS` | Không | Số lần retry ingest (mặc định 3) |
| `CHATBOT_INGEST_BACKOFF_SECONDS` | Không | Backoff giữa các lần retry (mặc định 5) |
| `CHATBOT_INGEST_BATCH_SIZE` | Không | Số slide mỗi request ingest (mặc định 8) |
| `R2_ACCOUNT_ID` / `R2_BUCKET_NAME` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` / `R2_PUBLIC_URL` | Không | Điền đủ 5 để lưu slide trên Cloudflare R2; để trống dùng volume local |
| `MEDIA_DIR` | Không | Thư mục media (mặc định `media`, tương đối theo cwd; Docker `/app/media`) |
| `MAX_UPLOAD_BYTES` | Không | Giới hạn file upload (mặc định 50MB) |
| `MAX_PDF_BYTES` | Không | Giới hạn PDF sau chuyển đổi (mặc định 100MB) |
| `MAX_SLIDE_PAGES` | Không | Số trang PDF tối đa (mặc định 150) |
| `LIBREOFFICE_TIMEOUT_SECONDS` | Không | Timeout LibreOffice (mặc định 120) |
| `WORKER_POLL_SECONDS` | Không | Chu kỳ poll analysis worker (mặc định 5) |
| `CONTENT_WORKER_POLL_SECONDS` | Không | Chu kỳ poll job chuyển slide (mặc định 3) |
| `DB_POOL_MIN` / `DB_POOL_MAX` | Không | Kích thước pool DB tối thiểu/tối đa (mặc định 5/20) |
| `MICROSOFT_CLIENT_ID` / `MICROSOFT_CLIENT_SECRET` / `MICROSOFT_TENANT_ID` | Không | Bật đăng nhập Microsoft 365 (single tenant). Để trống = tắt |
| `MICROSOFT_REDIRECT_URI` | Không | Phải khớp Redirect URI trong Azure App Registration |
| `MICROSOFT_ALLOWED_DOMAINS` | Không | Giới hạn domain email, phẩy phân tách |
| `FRONTEND_URL` | Không | Origin frontend để redirect sau OAuth callback |
| `DEBUG` | Không | Bật debug (mặc định `false`) |

## Endpoints chính

### Auth (`/api/auth`)
- `POST /api/auth/register` — **đã tắt** (403); tài khoản mới chỉ tạo qua Outlook
- `POST /api/auth/login` — chỉ dành cho tài khoản seed
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `POST /api/auth/change-password`
- `GET /api/auth/oauth/microsoft/start` — redirect sang Microsoft 365
- `GET /api/auth/oauth/microsoft/callback` — nhận code, đăng nhập/tạo tài khoản sinh viên

### Hồ sơ
- `GET/PATCH /api/me/profile`

### Admin (`/admin`)
- `GET /admin/students?q=` — danh sách sinh viên đang hoạt động
- `POST /admin/students/{user_id}/promote` — nâng cấp sinh viên lên giáo viên
  (thêm role `teacher`, bỏ role `student`, tạo `teacher_profiles`)

### Khóa học (giáo viên — `/teacher`)
- `GET/POST /teacher/courses`, `PATCH/DELETE /teacher/courses/{id}`
- `DELETE /teacher/courses/{id}` — xóa vĩnh viễn khóa học, nội dung, đăng ký, dữ liệu gaze/AOI và tệp R2.
- `GET /teacher/courses/{id}` — cây modules/lessons
- `GET /teacher/courses/{id}/draft`
- `POST /teacher/courses/{id}/publish` — chỉ thành công khi toàn bộ slide đã
  index xong cho trợ lý học tập; nếu còn slide lỗi/đang chờ, trả `409` kèm
  `code=slides_not_indexed` và **chạy nền** job index các slide thiếu (background
  task gắn vào response 409, không bị FastAPI bỏ khi raise exception).
- `PATCH /teacher/courses/{id}/gaze-dot`
- `PATCH /teacher/courses/{id}/require-calibration`
- `POST /teacher/courses/{id}/modules`, `PATCH/DELETE /teacher/modules/{id}`
- `POST /teacher/modules/{id}/lessons`, `PATCH/DELETE /teacher/lessons/{id}`
- `POST /teacher/modules/{id}/quizzes`
- `POST /teacher/modules/{id}/items/reorder`
- `GET /teacher/courses/{id}/students`
- `GET /teacher/students`
- `POST /teacher/courses/{id}/students`
- `DELETE /teacher/courses/{id}/students/{studentId}`

### Slide (giáo viên)
- `POST /teacher/lessons/{id}/slides/upload` — nhận PDF/PPTX/PPT/ODP, trả `202 {jobId}`
- `GET /teacher/lessons/{id}/slides/imports/{jobId}` — poll job
- `GET /teacher/lessons/{id}/slides`
- `POST /teacher/lessons/{id}/slides/reindex` — index lại các slide chưa sẵn
  sàng của bài giảng đang soạn (chạy nền)

### Phân tích (giáo viên)
- `GET /teacher/lessons/{id}/export` — JSONL analysis run hoàn tất mới nhất

### Học tập (sinh viên — `/api`)
- `GET /api/me/enrollments`
- `GET /api/courses/{id}` — outline
- `GET /api/lessons/{id}/contents` — slides
- `POST /api/learning-sessions`
- `PATCH /api/learning-sessions/{id}`
- `GET /api/learning-sessions/{id}/contents`
- `POST /api/learning-sessions/{id}/gaze-batches`
- `POST /api/learning-sessions/{id}/presentations`
- `POST /api/presentations/{id}/layouts`

### Bài tập trắc nghiệm
- `GET /api/quiz-specs/{lesson_version_id}`
- `GET/POST /api/lessons/{id}/attempts`
- `POST /api/attempts/{id}/submit`
- `POST /api/attempts/{id}/retry`
- `PATCH /teacher/quiz-specs/{id}` — `status: "published"` xuất bản course version
  nháp hiện tại để sinh viên thấy bài tập; `status: "draft"` chỉ lưu nháp.

`quizStatus` trong cây nội dung phản ánh việc sinh viên có thấy bài tập trong
**bản xuất bản** hay không, không dựa vào state của lesson version nháp. Vì vậy
sửa một bài tập đã giao không làm cảnh báo “còn ở bản nháp” hiện lại.

### Chatbot học tập
- `GET /api/courses/{id}/chat/access`
- `GET /api/courses/{id}/chat/sessions`
- `POST /api/courses/{id}/chat/stream` — SSE: `session → status → citations → token → done`
- `GET /api/chat/sessions/{id}/messages`
- `PATCH/DELETE /api/chat/sessions/{id}`

### AOI (giáo viên/admin)
- `GET/POST /api/aoi-sets`
- `PATCH /api/aoi-sets/{id}`
- `POST /api/aoi-sets/{id}/publish`
- `POST /api/aoi-sets/slide/{slide_version_id}/generate` — gợi ý `slide_n` + các vùng con `TEXT`/`IMAGE`/`TABLE` bằng PyMuPDF (mỗi block là một vùng)
  - `replaceAuto: true` — thay các vùng gợi ý tự động cũ, giữ vùng tự vẽ
  - `resetAll: true` — xoá cả vùng tự vẽ, chỉ giữ container `slide_n` rồi tạo lại các vùng gợi ý
- `PUT /api/aoi-sets/slide/{slide_version_id}` — lưu + áp dụng bộ vùng slide
- `POST /api/aoi-sets/ui/{ui_schema_version}/generate` — tạo bộ vùng giao diện
- `PUT /api/aoi-sets/ui/{ui_schema_version}` — lưu + áp dụng bộ vùng giao diện
- `POST /api/aoi/rebuild` — nhận `courseId`, `lessonId` tùy chọn; tạo run nền theo presentation

Mỗi bộ vùng luôn có định nghĩa hệ thống `no_label`; mẫu gaze không rơi vào vùng lá
nào được gán nhãn này. Phân tích chạy riêng cho slide và giao diện của từng
`content_presentation`.

Khi một mẫu gaze rơi vào nhiều vùng lá, backend chỉ ghi **một** hit theo thứ tự
ưu tiên `custom > text > table > image > drawing > system`. Nhờ vậy text đè lên
ảnh được tính là `TEXT`, không phải cả hai.

Vùng slide có thể được **bỏ đánh dấu** bằng `isActive = false`: định nghĩa vẫn
được giữ trong bộ vùng để bật lại, nhưng không tham gia matching; gaze trong vùng
đó được tính là `no_label`.

### Calibration
- `POST /api/calibrations` — lưu model `.ubj` + viewport/DPR + `screenXPx`/`screenYPx`
  (toạ độ viewport trên màn hình lúc calibration)
- `GET /api/calibrations/active`
- `GET /api/calibrations/active/model`

Frontend dùng hình chữ nhật vật lý của viewport lúc calibration và hiện tại để
quy đổi toạ độ gaze, nên zoom/resize/move cửa sổ không phải hiệu chỉnh lại.
Backend không chặn phiên học khi viewport khác calibration.

### Media
- `GET /media/assets/{id}/file` — proxy PDF same-origin cho PDF.js

### Nội bộ
- `POST /internal/chat/lms-query` — chatbot gọi backend
- `GET /ai/health` — probe gaze service

## Slide storage

- Upload nhận **PDF, PPTX, PPT, ODP**; mọi định dạng được chuẩn hóa thành một
  `source.pdf` duy nhất cho mỗi lần upload.
- Không lưu JPG: frontend dùng **PDF.js** render đúng trang từ PDF; mỗi trang là
  một `slide_version` với `source_page` tương ứng.
- Chuyển đổi chạy bất đồng bộ qua `slide_import_jobs` + service `content-worker`
  (LibreOffice headless trong image `content-worker`; API không cài LibreOffice).
- PDF được phục vụ same-origin qua `GET /media/assets/{id}/file`.

## Chatbot RAG

- Retrieval lọc `course_id` + `course_version_id` trước LIMIT; hybrid BM25
  (Postgres FTS) + vector (pgvector HNSW), fuse bằng RRF.
- Citation chứa `courseVersionId`, `lessonVersionId`, `slideVersionId`,
  `membershipId`, `assetId`, `pdfUrl`, `pageNumber`.
- Streaming SSE: `status → citations → token → done`.
- Mỗi tài khoản chỉ gửi được **1 tin nhắn mỗi 5 giây** (`POST
  /api/courses/{course_id}/chat/stream`); vượt quá trả `429` kèm `Retry-After`.
  Giới hạn theo user (không theo IP) nên áp dụng trên mọi thiết bị.

## Gaze

- Calibration 25 điểm → train model `.ubj` → lưu bất biến vào `calibrations`.
- WebSocket `/session/{sid}/stream` (qua nginx `/gaze/...`), protocol v2.
- Frontend gửi batch gaze qua `POST /api/learning-sessions/{id}/gaze-batches`.
- Worker `app.worker` tính `analysis_runs` + `presentation_metrics`.

## Content versioning

- Course/lesson/slide version bất biến sau publish; draft copy-on-write.
- `expectedGeneration` chống lost update.
- Publish chạy nền `embedding.sync_course_version` để ingest RAG.

## Lint và test

```bash
# Lint + compile
cd backend
.venv/bin/ruff check app
.venv/bin/python -m compileall -q app

# Integration test trên database tạm (từ gốc repo; cần postgres compose)
./scripts/test_backend.sh

# Test migration (baseline + schema_generation=8)
./scripts/test_migrations.sh
```

`scripts/test_backend.sh` tạo database `eyetracking_test`, chạy service
`migrate`, rồi chạy `pytest` trong `backend/.venv`. `scripts/test_migrations.sh`
kiểm tra đúng 1 migration và `schema_generation = 8`.
