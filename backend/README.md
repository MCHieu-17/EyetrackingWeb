# Backend — Eyetracking

FastAPI backend cho nền tảng học trực tuyến có gaze tracking. API, worker phân
tích, content-worker và embedding-worker dùng chung package `app`.

## Cấu trúc

```text
backend/app/
├── main.py              # FastAPI app, middleware, router, schema guard
├── worker.py            # entrypoint worker analyze_lesson
├── content_worker.py    # entrypoint worker import_slides
├── embedding_worker.py  # entrypoint worker index_slides
├── worker_loop.py       # vòng poll/log dùng chung
├── maintenance.py       # retention + dọn session hết hạn
├── api/
│   ├── deps.py          # auth, RBAC, rate-limit dependency
│   ├── access.py        # HTTP wrapper cho access policy
│   └── routes/          # transport/validation, prefix theo actor
├── core/                # config, security, CSRF, rate limit, logging
├── crud/                # truy vấn user/profile dùng chung
├── db/                  # SQLAlchemy session/Base/Redis
├── models/              # ánh xạ 24 bảng schema generation 13
├── schemas/             # Pydantic request/response (camelCase ở API)
├── services/
│   ├── access.py        # policy admin/owner/teacher/enrollment
│   ├── job_queue.py     # claim/recover background_jobs dùng chung
│   ├── content/         # course/module/lesson/slide/import
│   ├── analysis/        # analytics/export
│   ├── aoi/             # định nghĩa và generate AOI
│   ├── auth_flow.py     # token/cookie, refresh
│   ├── email_otp.py     # OTP đăng nhập sinh viên
│   ├── mailer.py        # gửi OTP qua SMTP
│   ├── media_access.py  # quyền tải PDF
│   ├── quiz.py          # ẩn/hiện đáp án, chấm điểm, hạn làm bài
│   ├── embedding*.py    # index RAG
│   ├── chat_context.py  # resolve lesson/quiz/attempt/session chat
│   ├── chat_payload.py  # payload/history gửi chatbot
│   ├── chat_transport.py# HTTP/SSE transport tới chatbot
│   ├── study_chat.py    # authorization + persistence + stream lifecycle
│   └── admin_db*.py     # read-only query, validation, serialization
```

Không còn bảng versioning nội dung. Sửa course/module/lesson/slide đã publish có
hiệu lực ngay; quiz đã bắt đầu giữ đề trong `quiz_attempts.quiz_snapshot`.

## Chạy

Docker (khuyến nghị):

```bash
docker compose up -d --build
```

Host:

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m uvicorn app.main:app --reload --port 8001
```

Backend đọc một file `.env` ở gốc repo. Các biến bắt buộc tối thiểu:
`DATABASE_URL` (host) hoặc `DATABASE_URL_DOCKER` (compose), `JWT_SECRET`,
`CORS_ORIGINS`, `AI_HTTP_URL`. Xem đầy đủ trong `.env.example` và
`app/core/config.py`.

## Worker và job

Tất cả job dùng bảng `background_jobs` với `kind`:

| Kind | Worker | Việc |
|---|---|---|
| `import_slides` | `content-worker` | convert PDF/PPTX/PPT/ODP → PDF, thay slides |
| `index_slides` | `embedding-worker` | gọi chatbot ingest/embedding |
| `analyze_lesson` | `worker` | quy đổi gaze, matching AOI, metrics |

Worker claim job bằng `FOR UPDATE SKIP LOCKED`. Claim/recovery dùng chung nằm ở
`services/job_queue.py`; payload và xử lý từng loại vẫn tách riêng. Job
`processing` quá stale được đưa lại queue cho tới `max_attempts`.

Hai target Docker:

| Target | Dùng cho | Nội dung |
|---|---|---|
| `api` | backend, worker, embedding-worker | FastAPI/runtime, không LibreOffice |
| `content-worker` | content-worker | thêm LibreOffice + fonts |

## Luồng chính

### Giáo viên

`/teacher/...` quản lý course/module/lesson/quiz/slide/student. Upload slide trả
`202 {jobId}`, frontend poll job import. Publish validate toàn bộ nội dung rồi
đổi `courses.status='published'`; không tạo snapshot.

### Học viên

1. `POST /api/learning-sessions` mở phiên học.
2. Mỗi slide/quiz tạo `content_views`; endpoint dùng tên domain
   `/presentations` và trả `presentationId`. Frontend gửi
   `clientPresentationId`/`enteredAt`; server cấp `sequence_no` và luôn tạo
   lượt mới khi vào lại slide, không ghi đè row cũ.
3. Lượt xem ngắn hơn `CONTENT_VIEW_MIN_DWELL_MS` vẫn được trả về mặc định
   (`includeShort=true`), chỉ gắn cờ `counted=false`. `includeShort=false`
   dùng cho bộ lọc tùy chọn.
4. Resize/mở chat tạo `view_layouts`.
5. Frontend batch gaze vào `POST /api/learning-sessions/{id}/gaze-batches`.
6. Đóng phiên enqueue `analyze_lesson`.

Gaze thô (`viewport_x/y`, `event_time`) là bất biến. `slide_x/y`, `aoi_label`,
metrics là derived và có thể tính lại.

### Chatbot

Backend lưu lịch sử `chat_sessions/chat_messages`, gọi chatbot nội bộ qua
`CHATBOT_URL` + `CHATBOT_INTERNAL_TOKEN`. SSE giữ transaction DB ngắn, không giữ
connection trong suốt thời gian stream.

### Đăng nhập sinh viên

Sinh viên dùng `POST /api/auth/otp/request` để nhận mã 6 số qua email trường
(`@st.neu.edu.vn`), sau đó `POST /api/auth/otp/verify` để nhận token/cookie.
OTP lưu dạng hash, hết hạn 15 phút, tối đa 5 lần nhập. Không còn Microsoft
OAuth/`oauth_accounts`.

### Admin

`/admin/...` quản lý user và truy vấn DB read-only qua `admin_reader`:
transaction read-only, statement/lock timeout, giới hạn dòng/response, không
đọc password/auth/OTP.

## API docs

Swagger ở `/docs`, OpenAPI ở `/openapi.json` khi backend chạy. Route module là
nguồn sự thật; tài liệu này chỉ mô tả nhóm chính để tránh lặp danh sách endpoint
bị lệch.

Frontend và backend dùng thống nhất `slideId`, `lessonId`, `presentationId`,
`layoutId`. Không có bảng `*_versions`. Xem `AGENTS.md` trước khi đổi contract.

## Database

- Schema generation 13, 24 bảng lõi.
- `001_baseline.sql` (generation 12) + `002_email_otp.sql` +
  `003_aoi_single_label.sql` + `004_content_view_aoi_stats.sql` +
  `005_current_viewport_only.sql`.
- Backend fail-fast nếu `app_metadata.schema_generation != '13'`.
- Không sửa migration đã áp; thay đổi mới phải là `006_...`.
- Cascade/FK là cơ chế xoá dữ liệu liên quan. File media local/R2 được dọn sau
  transaction DB.
- Từ điển bảng/ERD và quy ước schema: `AGENTS.md`.

## Lint và kiểm tra schema

```bash
# Từ root
./scripts/check.sh --full
./scripts/test_migrations.sh

# Trực tiếp
cd backend
.venv/bin/ruff check app
```

## Test

Fast test dùng PostgreSQL/Redis test thật, mock chatbot/LLM; chạy trong image
`backend-test` (dev deps), không cần venv host:

```bash
# Từ root
./scripts/test_backend.sh
make test-fast

# Một file cụ thể
./scripts/test_backend.sh tests/fast/test_quiz.py -q
```

Phạm vi hộp đen và nhóm `fast`/`smoke`: mục 2 `AGENTS.md`.
