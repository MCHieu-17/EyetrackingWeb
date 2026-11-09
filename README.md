# GazeEdu — EyeLearning

Nền tảng học tập theo dõi hành vi mắt (eye-tracking): học viên học bài giảng slide
qua webcam, hệ thống ước lượng hướng nhìn và sinh phân tích mức độ tập trung cho
giáo viên.

> **Repo này chỉ chạy LOCAL.** Không có CI/CD, không GHCR, không Cloudflare Tunnel,
> không Portainer. Toàn bộ image được build từ source trên máy bạn.

## Kiến trúc

```
┌────────────┐   HTTP/WS    ┌────────────┐   SQL    ┌────────────┐
│  frontend  │ ───────────► │  backend   │ ───────► │  postgres  │
│  Next.js   │              │  FastAPI   │          │  (5435)    │
│  (:3000)   │              │  (:8001)   │          └────────────┘
└─────┬──────┘              └─────┬──────┘
      │  WS /session/{sid}/stream  │ calibration (JSON base64: model .ubj)
      ▼                            ▼
┌────────────────────┐      lưu model .ubj active theo (user, device)
│ services/gaze (ML) │
│  (:8000, GPU)      │  mediapipe + UniGaze gaze estimation
│                    │  calibration 25 điểm → train model → .ubj
└────────────────────┘

      │  POST /api/courses/{id}/chat/stream (SSE)
      ▼
┌────────────────────┐
│ services/chatbot   │  LangChain + pgvector hybrid search (BM25 + vector)
│  (:8002, CPU)      │  DeepSeek qua River AI + Qwen3-Embedding-0.6B (CPU)
└────────────────────┘
```

| Thư mục | Vai trò |
|---|---|
| `frontend/` | Next.js (App Router, TypeScript, Tailwind) — khu vực học viên + giáo viên |
| `backend/` | FastAPI — auth/JWT, khóa học, gaze ingestion, analytics, proxy chat |
| `services/gaze/` | ML service — ước lượng gaze từ webcam, calibration, WebSocket (cần GPU) |
| `services/chatbot/` | RAG service — ingest slide bằng VLM, hybrid retrieval, citation, SSE (embedding CPU) |
| `db/` | Migrations PostgreSQL — một baseline `001_baseline.sql`, schema generation 8 |
| `nginx/` | Reverse proxy local: web :3000 → frontend/backend/gaze |
| `scripts/` | Seed/reset/test + tạo role chatbot, bảo trì partition, dọn Docker |

## Chạy nhanh (Full Docker)

Yêu cầu: Docker + Docker Compose v2. Nếu dùng GPU: NVIDIA driver +
`nvidia-container-toolkit`.

```bash
# 1) Tạo file env local
cp .env.example .env
#    Điền các secret bắt buộc: POSTGRES_PASSWORD, JWT_SECRET,
#    CHATBOT_INTERNAL_TOKEN, CHATBOT_DB_PASSWORD, RIVER_API_KEY...
#    Nếu đổi POSTGRES_PASSWORD/CHATBOT_DB_PASSWORD, sửa cả DSN tương ứng.
#    Khối R2 để trống nếu dùng volume local; các biến tuning còn lại đã có
#    default trong compose.

# 2) Build + chạy stack
docker compose up -d --build

# 3) Mở web
#    http://localhost:3000
```

`docker compose up -d --build` build toàn bộ image từ Dockerfile của từng
service. Build riêng một service:

```bash
docker compose build backend
docker compose up -d backend
```

Lần đầu gaze/chatbot sẽ tải weights vào volume (có thể vài phút). Theo dõi:

```bash
docker compose logs -f gaze
docker compose logs -f chatbot
```

### Tài khoản mẫu (chỉ dev — mật khẩu `Password123!`)

```bash
./scripts/seed_dev.sh
```

| Email | Vai trò |
|---|---|
| `admin@school.edu.vn` | Quản trị viên |
| `teacher@school.edu.vn` | Giáo viên |
| `student@school.edu.vn` | Học sinh |

Có thể tự đổi mật khẩu tại `/account/change-password` (không bắt buộc).

### Đăng nhập bằng Microsoft 365 (Outlook)

Hệ thống hỗ trợ đăng nhập/đăng ký bằng tài khoản Microsoft 365 của trường
(single tenant). Tài khoản tạo mới mặc định là **sinh viên**.

Đăng nhập bằng email/mật khẩu chỉ còn dành cho các **tài khoản seed** trong
`db/seed_dev_users.sql`. Đăng ký bằng mật khẩu đã bị tắt hoàn toàn
(`POST /api/auth/register` trả `403`).

Cấu hình trong `.env`:

```env
MICROSOFT_CLIENT_ID=<Application (client) ID>
MICROSOFT_CLIENT_SECRET=<client secret>
MICROSOFT_TENANT_ID=<Directory (tenant) ID>
MICROSOFT_REDIRECT_URI=http://localhost:3000/api/auth/oauth/microsoft/callback
FRONTEND_URL=http://localhost:3000
```

Đăng ký app trên Azure:

1. Microsoft Entra ID → App registrations → New registration.
2. Chọn **Accounts in this organizational directory only** (single tenant).
3. Redirect URI (Web): `http://localhost:3000/api/auth/oauth/microsoft/callback`
   (và URL production nếu có).
4. Certificates & secrets → tạo client secret.
5. API permissions: `openid`, `profile`, `email`, `User.Read`.
6. Điền client ID, tenant ID, client secret vào `.env` rồi build lại backend.

Nếu để trống `MICROSOFT_CLIENT_ID` / `MICROSOFT_CLIENT_SECRET` /
`MICROSOFT_TENANT_ID`, nút Outlook vẫn hiển thị nhưng báo “chưa được cấu hình”.

### Nâng cấp sinh viên lên giáo viên

Trang `/admin` chỉ dành cho quản trị viên:

- Tìm sinh viên theo tên, email hoặc mã sinh viên.
- Bấm **Nâng cấp**, nhập mã giảng viên (để trống để tự sinh `GV0001`, `GV0002`…)
  và khoa/bộ môn.
- Sau khi nâng cấp, tài khoản nhận role `teacher`, mất role `student` và cần
  đăng nhập lại để thấy khu vực giảng viên.

## GPU

- **Gaze là service duy nhất cần GPU.** Compose đặt `gpus: all` cho `gaze`,
  `DEVICE=cuda`; stage `ai-base` trong `services/gaze/Dockerfile` cài
  torch/torchvision CUDA 12.4. Host cần NVIDIA driver +
  `nvidia-container-toolkit`.
- **Chatbot chạy CPU.** `EMBEDDING_DEVICE=cpu`; stage `ai-base` trong
  `services/chatbot/Dockerfile` cài torch CPU (nhẹ hơn nhiều); LLM/VLM gọi
  River API. Chatbot **không** đặt `gpus: all` và không cần NVIDIA driver.
- Không có GPU: đặt `DEVICE=cpu` trong `.env` và bỏ `gpus: all` ở service
  `gaze` trong `docker-compose.yml`. Gaze vẫn chạy nhưng rất chậm; chatbot
  không bị ảnh hưởng.

## Cổng

Các cổng debug (`8000`, `8001`, `8002`) chỉ bind `127.0.0.1`, không mở ra LAN.

| Cổng | Dịch vụ |
|---|---|
| `3000` | nginx → web (frontend + /api + /media + /gaze) |
| `8000` | gaze (debug trực tiếp, chỉ loopback) |
| `8001` | backend (Swagger: `/docs`, chỉ loopback) |
| `8002` | chatbot (debug trực tiếp, chỉ loopback) |
| `5435` | postgres (chỉ loopback) |
| `6379` | redis (chỉ loopback) |

## Lệnh thường dùng

```bash
# Xem trạng thái
docker compose ps

# Log
docker compose logs -f backend
docker compose logs -f content-worker
docker compose logs -f frontend
docker compose logs -f nginx

# Build lại toàn bộ hoặc một service
docker compose build
docker compose build backend

# Sửa code backend/frontend → build lại service tương ứng
docker compose up -d --build backend
docker compose up -d --build content-worker
docker compose up -d --build frontend

# Sửa code gaze/chatbot → build lại
docker compose up -d --build gaze
docker compose up -d --build chatbot

# Dừng (giữ dữ liệu)
docker compose stop

# Dừng + xóa container (giữ volume)
docker compose down

# XÓA CẢ VOLUME — mất DB + weights, chỉ dùng khi thật sự muốn reset sạch
docker compose down -v
```

> **Không có hot reload trong Docker.** Mỗi lần sửa code phải build lại service.
> Nếu muốn hot reload, chạy backend/frontend trên host:
> `cd backend && .venv/bin/python -m uvicorn app.main:app --reload --port 8001`
> và `cd frontend && npm run dev` (Docker chỉ chạy postgres/redis/gaze/chatbot).

## Migrations

Schema chuẩn là **một baseline sạch**:

- `db/migrations/001_baseline.sql` — toàn bộ schema/constraint/index/trigger/view
  + reference seed (roles, cấu hình hệ thống, `user_identities` cho Microsoft 365).

Không còn migration delta. Khi schema thay đổi, thêm file mới `002_...sql`;
không sửa file đã áp. Schema generation hiện tại là `8`.

Service `migrate` tự chạy mỗi lần `docker compose up`. Runner `db/migrate.sh`:

- Một kết nối giữ advisory lock suốt lượt chạy.
- Ghi file đã áp + checksum vào `schema_migrations` trong cùng transaction.
- Chỉ chạy file chưa áp; file đã áp bị sửa → fail.
- DB có lịch sử migration cũ / schema cũ → fail, yêu cầu reset có guard.

Chạy tay:

```bash
docker compose run --rm migrate
```

Reset DB development (mặc định chỉ preview):

```bash
./scripts/reset_db.sh
./scripts/reset_db.sh --apply --database eyetracking --confirm-reset eyetracking --seed-dev
```

Quy tắc: **không sửa file migration đã áp** — thêm file mới (`002_...`).
Schema hiện tại là `schema_generation = 8`; DB cũ sẽ fail-fast và cần chạy
migration (hoặc reset có guard).

## Slide storage

- Upload nhận **PDF, PPTX, PPT, ODP**; mọi định dạng được chuẩn hóa thành một
  `source.pdf` duy nhất cho mỗi lần upload.
- Không lưu JPG: frontend dùng **PDF.js** render đúng trang từ PDF; mỗi trang là
  một `slide_version` với `source_page` tương ứng.
- Chuyển đổi chạy bất đồng bộ qua `slide_import_jobs` + service `content-worker`
  (LibreOffice headless trong image `content-worker`; API không cài LibreOffice).
- PDF được phục vụ same-origin qua `GET /media/assets/{id}/file` để tránh CORS
  và presigned URL hết hạn.

## Chatbot RAG

Service `migrate` tự tạo/cập nhật role DB hạn chế cho chatbot sau mỗi lần áp
migrations (đọc `CHATBOT_DB_USER`/`CHATBOT_DB_PASSWORD` từ `.env`). Không cần
chạy tay; nếu muốn cấp lại quyền ngay mà không chạy migration:

```bash
./scripts/create_chatbot_role.sh
```

- Ingest chia slide thành batch nhỏ (`CHATBOT_INGEST_BATCH_SIZE`, mặc định 8)
  để bài dài không vượt timeout; slide đã `ready` không bị ingest lại.
- Lỗi DB/role của chatbot trả `503` kèm lý do thật (thay vì `500`), backend lưu
  lý do vào `slide_documents.ingestion_error` để UI hiển thị.
- Retrieval lọc `course_id` + `course_version_id` **trước LIMIT**; hybrid BM25
  (Postgres FTS) + vector (pgvector HNSW), fuse bằng RRF.
- Model: DeepSeek V4.1 Flash qua River AI cho router/answer/verifier/VLM;
  embedding local `Qwen3-Embedding-0.6B` chạy **CPU** (1024 chiều). Chatbot
  không dùng GPU — GPU chỉ dành cho gaze.
- Citation chứa `courseVersionId`, `lessonVersionId`, `slideVersionId`,
  `membershipId`, `assetId`, `pdfUrl`, `pageNumber`; verifier kiểm tra evidence quote.
- Streaming SSE: `status → citations → token → done`.
- Chat quiz dùng đúng `attemptId`; attempt đã nộp cũ không mở quyền attempt mới.

## Gaze

- Calibration 25 điểm → train model `.ubj` → lưu bất biến vào `calibrations`;
  `devices.current_calibration_id` trỏ bản mới nhất.
- Model dùng được với mọi viewport: frontend quy đổi toạ độ gaze từ viewport
  lúc calibration sang viewport hiện tại (zoom/resize/move cửa sổ), không cần
  hiệu chỉnh lại.
- WebSocket `/session/{sid}/stream` (qua nginx `/gaze/...`), protocol v2:
  4-byte header length + JSON header + JPEG; echo `frameId`/`sequence`.
- Frontend gửi batch idempotent vào `gaze_samples` (partition theo tháng);
  IndexedDB queue giữ batch tới khi ACK.
- Gaze cần GPU theo mặc định (`gpus: all`, `DEVICE=cuda`). Không có GPU: đặt
  `DEVICE=cpu` và bỏ `gpus: all` ở service `gaze` — chạy được nhưng chậm.
  Chatbot luôn chạy CPU (`EMBEDDING_DEVICE=cpu`), không dùng GPU.

## Lint

```bash
# Frontend
cd frontend && npm run lint && npm run typecheck

# Ruff
ruff check backend services/gaze services/chatbot
```

## Bảo trì partition

Baseline tạo partition tháng trước/current/3 tháng tới + default partition.
Khi cần tạo thêm:

```bash
./scripts/create_partitions.sh 3
```

Worker `worker` chạy `analysis_runs` pending; watermark/trạng thái nằm trong
PostgreSQL nên restart không mất việc.

## Backup & bảo trì

```bash
./scripts/backup.sh                   # backup DB → backups/eyelearning-*.dump
./scripts/backup.sh --restore <file>  # restore (hỏi xác nhận, trừ khi --yes)
./scripts/maintenance.sh              # dọn session hết hạn (bảo trì định kỳ)
```

Xem chi tiết backup/restore, logging (`LOG_FORMAT=json`, `LOG_LEVEL`) và cảnh
báo `docker compose down -v` tại
[`docs/cleanup/OPERATIONS.md`](docs/cleanup/OPERATIONS.md).

## Dọn dung lượng Docker

```bash
./scripts/docker_cleanup.sh   # chỉ prune image/build cache, KHÔNG đụng volume

# Xóa image GHCR cũ (nếu còn từ trước khi chuyển sang local)
docker image rm ghcr.io/manh1504/eyelearning-{backend,frontend,nginx,migrations,gaze,chatbot}:latest
```

## Xử lý sự cố

| Lỗi | Cách xử lý |
|---|---|
| Build gaze/chatbot lỗi torch/CUDA | Xem log `docker compose build gaze` / `chatbot`; kiểm tra wheel trong `requirements-torch*.txt` |
| Build lỗi do thiếu BuildKit | Kiểm tra `docker buildx version`; Docker Compose v2 dùng BuildKit mặc định |
| `gpus: all` lỗi / không có GPU | Chỉ `gaze` dùng GPU: bỏ `gpus: all` ở `gaze`, đặt `DEVICE=cpu`. Chatbot luôn CPU |
| Cổng 3000 đang dùng | `docker compose stop nginx` hoặc dừng process đang giữ cổng |
| Cổng 8001/8000/8002 đang dùng | `ss -ltnp \| grep -E '8000\|8001\|8002'` rồi dừng process |
| Login không giữ phiên | `.env` phải có `COOKIE_SECURE=false`, rebuild backend |
| Backend `connection refused` tới DB | `docker compose ps` — postgres chưa healthy |
| Migration lỗi | `docker logs eyetracking-migrate`; sửa file mới, không sửa file đã áp |
| Content-worker không chuyển được slide | `docker compose logs -f content-worker`; kiểm tra LibreOffice trong image `content-worker` |
| Chatbot chưa `/ready` | Chờ tải weights; `docker compose logs -f chatbot` |
| Gaze chưa `/ready` | Chờ tải weights + load model; `docker compose logs -f gaze` |
| Hết dung lượng Docker | `./scripts/docker_cleanup.sh` (không xóa volume) |

## Cấu trúc image local

| Image | Build từ |
|---|---|
| `eyelearning-migrations:local` | `db/Dockerfile` (context `./db`) |
| `eyelearning-backend:local` | `backend/` target `api` |
| `eyelearning-backend-content-worker:local` | `backend/` target `content-worker` (LibreOffice) |
| `eyelearning-frontend:local` | `frontend/` |
| `eyelearning-nginx:local` | `nginx/` |
| `eyelearning-gaze:local` | `services/gaze/` (multi-stage: `ai-base` + `runtime`) |
| `eyelearning-chatbot:local` | `services/chatbot/` (multi-stage: `ai-base` + `runtime`) |

## Ghi chú

- `.env` chứa secret và đã được gitignore — không commit.
- Chỉ có **một file `.env` ở gốc repo** cho backend/frontend/chatbot/gaze.
- Nếu login không giữ phiên trên `http://localhost`: đặt `COOKIE_SECURE=false`
  trong `.env` rồi `docker compose up -d --build backend`.
- Nếu `npm run dev` báo cổng 3000 đang dùng: `docker compose stop nginx`.
