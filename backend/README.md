# Backend — GazeEdu (EyeLearning)

FastAPI backend cho hệ thống học tập theo dõi hành vi mắt (eye-tracking).

## Kiến trúc

```
backend/app/
├── main.py              # FastAPI app, CORS, routers
├── core/
│   ├── config.py        # Settings (pydantic-settings, đọc .env)
│   ├── security.py      # bcrypt + JWT (access/refresh)
│   └── helpers.py       # gradient/color palette, relative time tiếng Việt
├── db/
│   ├── base.py          # SQLAlchemy Base
│   └── session.py       # async engine + session (asyncpg)
├── models/              # SQLAlchemy models ánh xạ db/migrations/*.sql
├── schemas/             # Pydantic v2 — camelCase, khớp frontend/lib/types/domain.ts
├── crud/                # data access
├── services/            # course_stats (aggregate), analytics (heatmap/fixation/hotspot)
└── api/
    ├── deps.py          # get_current_user, require_roles (RBAC)
    ├── access.py        # helper dùng chung: course/module/lesson + calibration
    └── routes/          # auth, users, courses, modules, lessons, enrollments,
                         # gaze, calibration, analytics, proxy (AI service)
```

## Chạy

### Cách 1: Docker Compose (khuyến nghị)

```bash
docker compose up -d --build    # cả stack (postgres, migrate, backend, frontend, nginx, ...)
```

### Cách 2: Chạy trực tiếp (dev)

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
# Dùng MỘT file env duy nhất ở gốc repo: copy .env.example .env (gốc repo)
.venv/bin/python -m uvicorn app.main:app --port 8001 --reload
```

Yêu cầu PostgreSQL đang chạy (`docker compose up -d postgres` từ gốc repo).

## Cấu hình (env — một file duy nhất ở gốc repo)

Backend đọc mọi biến từ **`.env` ở gốc repo** (`backend/app/core/config.py` trỏ thẳng
tới `ROOT_ENV_FILE`). Không còn giá trị mẫu nhúng trong code.

| Biến | Bắt buộc | Ý nghĩa |
|---|---|---|
| `DATABASE_URL` | Chỉ host | Chuỗi kết nối PG (asyncpg) khi chạy backend ngoài container |
| `DATABASE_URL_DOCKER` | Có (compose) | Chuỗi kết nối DB nội bộ cho container backend |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Có (compose) | Tạo DB của service `postgres` |
| `JWT_SECRET` | Có | Chuỗi random dài; không dùng giá trị mẫu |
| `JWT_ALGORITHM` | Không | Mặc định `HS256` trong code; không cần đặt trong `.env` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Không | Mặc định 60 trong code |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Không | Mặc định 30 trong code |
| `CORS_ORIGINS` | Có | Phân tách bằng dấu phẩy |
| `AI_HTTP_URL` | Có (compose) | Gaze service; compose tự set `http://gaze:8000` |
| `CHATBOT_URL` | Chỉ host | Chatbot service khi backend chạy host (`http://localhost:8002`) |
| `CHATBOT_INTERNAL_TOKEN` | Có (nếu dùng chat) | Token nội bộ backend → chatbot |
| `CHATBOT_TIMEOUT_SECONDS` | Không | Timeout gọi chatbot (mặc định 120) |
| `CHATBOT_INGEST_TIMEOUT_SECONDS` | Không | Timeout ingest slide (mặc định 600) |
| `CHATBOT_INGEST_ATTEMPTS` | Không | Số lần retry ingest (mặc định 3) |
| `CHATBOT_INGEST_BACKOFF_SECONDS` | Không | Backoff giữa các lần retry (mặc định 5) |
| `GAZE_DOWNSAMPLE_HZ` | Không | Downsample `gaze_events` trước khi ghi DB (mặc định 4.0) |
| `GAZE_RAW_HZ` | Không | Tần số lưu `gaze_raw_samples` (mặc định 15.0; `0` = lưu tất cả) |
| `GAZE_BATCH_MAX` | Không | Batch gaze tối đa (mặc định 2000) |
| `R2_ACCOUNT_ID` / `R2_BUCKET_NAME` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` / `R2_PUBLIC_URL` | Không | Điền đủ 5 để lưu slide trên Cloudflare R2; để trống dùng volume local |
| `DEBUG` | Không | Bật debug (mặc định `false`) |

## Endpoints chính

### Auth (`/api/auth`)
- `POST /api/auth/login` — `{email, password}` → `{accessToken, refreshToken, user}`
- `POST /api/auth/refresh` — rotate refresh token
- `POST /api/auth/logout` — revoke refresh token

### Hồ sơ
- `GET/PATCH /api/me/profile` — khớp `MyProfile`/`ProfileUpdate` của frontend

### Khóa học (giáo viên — `/teacher`)
- `GET/POST /teacher/courses`, `PATCH/DELETE /teacher/courses/{id}`
- `POST /teacher/courses/{id}/modules`, `PATCH/DELETE /teacher/modules/{id}`
- `POST /teacher/modules/{id}/lessons`, `PATCH/DELETE /teacher/lessons/{id}`
- `POST /teacher/modules/{id}/quizzes` — tạo nhanh item bài tập trắc nghiệm (nháp) trong chương
- `POST /teacher/modules/{id}/items/reorder` — sắp xếp lại item (bài học + bài tập) trong chương
- `POST /teacher/lessons/{id}/slides`, `DELETE /teacher/slides/{id}`
- `GET /teacher/courses/{id}` — cây modules/lessons (kèm `kind`, thông tin quiz) + attention
- `GET /teacher/courses/{id}/students` — danh sách học viên + mức quan sát từng bài
- `GET /teacher/lessons/{id}/heatmap?studentId=` — SlideStat[] (onSlide, fixations, viewSec, hotspots)
- `POST /teacher/courses/{id}/recompute` — batch tính lại `heatmap_aggregates` + `engagement_scores`

### Bài tập trắc nghiệm (`/api/assignments`)
- `GET /api/assignments/{id}` — nội dung bài tập (ẩn đáp án khi học viên chưa nộp; tạo phiên làm bài để đếm ngược theo `durationMinutes`); trả `allowRetry` để UI biết có được làm lại không
- `PATCH /api/assignments/{id}` — sửa câu hỏi/tiêu đề/thời lượng/hạn nộp/trạng thái/`allowRetry`; publish cần ≥1 câu hỏi. Câu hỏi hỗ trợ nhiều đáp án đúng (`correctOptionIds`, `allowMultiple`) và chấm **tất cả-hoặc-không**.
- `GET /api/assignments/{id}/attempt` / `POST /api/assignments/{id}/attempts` — nộp bài (mỗi học viên một lần)
- `POST /api/assignments/{id}/retry` — **làm lại**: chỉ khi giáo viên bật `allowRetry` và bài còn mở; xoá lượt làm cũ, đặt lại đồng hồ làm bài (đáp án bị ẩn lại cho tới lần nộp kế tiếp)

Bài tập là một `lessons.kind='quiz'`; mọi item trong chương dùng chung `order_index` nên thứ tự bài học/bài tập được trộn theo đúng thiết kế khóa học.

### Chatbot học tập (`/api/courses/{id}/chat`, `/api/chat/sessions`)
- `GET /api/courses/{id}/chat/sessions` — phiên chat của sinh viên trong môn.
- `POST /api/courses/{id}/chat` — hỏi đáp non-streaming; trả `{answer, citations, intent, verified}`.
- `POST /api/courses/{id}/chat/stream` — SSE: `session → status → citations → token → done`.
- `GET /api/chat/sessions/{id}/messages` — lịch sử tin nhắn.
- `PATCH/DELETE /api/chat/sessions/{id}` — đổi tên/xoá phiên.
- `POST /teacher/lessons/{id}/reindex`, `POST /teacher/courses/{id}/reindex` — ingest lại slide.
- `GET /teacher/courses/{id}/embedding-status` — đếm slide theo trạng thái embedding.

Backend dựng ngữ cảnh bài tập: trước khi nộp chỉ gửi đề + options + đáp án đã chọn
(không gửi đáp án đúng); sau khi nộp mới gửi đáp án + giải thích để chữa bài.

### Học tập (sinh viên — `/api`)
- `GET /api/me/enrollments`
- `POST /api/courses/{id}/enroll`
- `GET /api/courses/{id}` — outline
- `GET /api/lessons/{id}/contents` — slides
- `POST /api/learning-sessions` — bắt buộc `viewportWidthPx/HeightPx`, `calibrationWidthPx/HeightPx`, `devicePixelRatio`; viewport phải bằng calibration (nếu không → `409 viewport_mismatch`)
- `PATCH /api/learning-sessions/{id}` — đóng phiên
- `POST /api/lessons/{id}/gaze-samples` — batch `{samples: [{lessonContentId, x, y, slideX?, slideY?, faceDetected, ts}], viewportWidthPx, viewportHeightPx, layoutSnapshotId?}`. `x/y` là toạ độ RAW theo viewport (có thể <0/>1); `slideX/slideY` dùng cho `gaze_events`/analytics cũ. Backend ghi `gaze_raw_samples` (downsample `GAZE_RAW_HZ`) + `gaze_events` (downsample `GAZE_DOWNSAMPLE_HZ`). Viewport lệch calibration → `409 viewport_mismatch`.
- `POST /api/learning-sessions/{id}/aoi-layout` — frontend gửi rect thật của mọi `[data-aoi]`; tạo `aoi_layout_snapshots` + `aoi_layout_rects`

### AOI (giáo viên/admin)
- `GET /api/aoi-definitions?include_inactive=` — catalog AOI toàn hệ thống
- `POST /api/aoi-definitions` — `{code, name, description?, parentId?, selector?}`
- `PATCH /api/aoi-definitions/{id}` — sửa tên/mô tả/parent/selector/isActive
- `DELETE /api/aoi-definitions/{id}` — soft delete (`isActive=false`)
- `POST /api/aoi/rebuild` — `{sessionId?, lessonId?, courseId?, fromTime?, toTime?}`; tính lại `gaze_aoi_hits` từ raw + snapshot rects

### Calibration
- `POST /api/calibrations` — JSON `{deviceFingerprint, numPoints, modelUbjBase64, maePx?, screenWidthPx?, screenHeightPx?}` — `modelUbjBase64` là file `.ubj` tải từ `GET /session/{sid}/model` của gaze service (base64, ~1-3KB); bất kỳ bản cũ nào của (user, device) tự deactivate. Ghi vào `calibration_params.model_ubj`.
- `GET /api/calibrations/active?deviceFingerprint=` — metadata bản active (`calibrated`, `maePx`, `calibratedAt`)
- `GET /api/calibrations/active/model?deviceFingerprint=` — `{modelUbjBase64, maePx}` của bản active để client nạp lại qua `POST /session/{sid}/import` (không cần hiệu chỉnh lại). `409` nếu bản ghi cũ chỉ có 6 tham số kappa.
- `GET /api/calibrations/config` — ngưỡng `maePx` pass/fail do admin đặt.

### AI service — kết nối trực tiếp
- WebSocket `/session/{sid}/stream` và toàn bộ `POST /session...` của gaze service **gọi trực tiếp** (frontend → nginx `/gaze/*` → gaze; backend không proxy). Backend chỉ lưu model `.ubj` và kiểm soát quyền.
- `GET /ai/health` — backend probe ML service còn sống không.

## Thiết kế đáng chú ý

- **JWT access ngắn hạn + refresh token** lưu dạng SHA-256 hash trong `auth_sessions`, rotation khi refresh.
- **RBAC**: role trong JWT + kiểm tra `user_roles`; ownership khóa học theo `courses.owner_id`.
- **Content versioning**: course/lesson/slide version bất biến sau publish; draft copy-on-write; `expectedGeneration` chống lost update.
- **Gaze**: một nguồn `gaze_samples` (viewport raw, partition theo tháng); `gaze_batches` giữ ACK/idempotency; metadata calibration/viewport/pipeline nằm ở session/batch, không lặp trên từng sample.
- **AOI/analysis**: `aoi_sets` versioned; `analysis_runs` chốt watermark + time range; `aoi_hits`/`presentation_metrics` là derived, rebuild theo run.
- **Chat/RAG**: retrieval lọc `course_version_id` trước LIMIT; citation chứa version/membership/asset IDs; quiz hint/review theo đúng `attemptId`.
- **Heatmap**: fixation detection (dispersion) + hotspot clustering (grid 24×24 + local maxima) tính on-the-fly từ `gaze_events`; `heatmap_aggregates`/`engagement_scores` được tự refresh gần thời gian thực sau mỗi batch gaze-sample (incremental, chỉ chạm slide của batch) + endpoint recompute (batch) để chạy lại toàn bài.
- **camelCase**: toàn bộ response dùng alias generator `to_camel` — khớp `frontend/lib/types/domain.ts`, UI không cần sửa.
