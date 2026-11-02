# GazeEdu — EyeLearning

Nền tảng học tập theo dõi hành vi mắt (eye-tracking): học viên học bài giảng slide
qua webcam, hệ thống ước lượng hướng nhìn và sinh phân tích (heatmap, mức độ tập
trung) cho giáo viên.

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
│  (:8000)           │  mediapipe + UniGaze gaze estimation
│                    │  calibration 16 điểm → train model → .ubj
└────────────────────┘

      │  POST /api/courses/{id}/chat/stream (SSE)
      ▼
┌────────────────────┐
│ services/chatbot   │  LangChain + pgvector hybrid search (BM25 + vector)
│  (:8002)           │  DeepSeek qua River AI + Qwen3-Embedding-0.6B local
└────────────────────┘
```

| Thư mục | Vai trò |
|---|---|
| `frontend/` | Next.js (App Router, TypeScript, Tailwind) — khu vực học viên + giáo viên |
| `backend/` | FastAPI — auth/JWT, khóa học, gaze ingestion, analytics, proxy chat |
| `services/gaze/` | ML service — ước lượng gaze từ webcam, calibration, WebSocket (cần GPU) |
| `services/chatbot/` | RAG service — ingest slide bằng VLM, hybrid retrieval, citation, SSE |
| `db/` | Migrations PostgreSQL (001 → 024) |
| `nginx/` | Reverse proxy local: web :3000 → frontend/backend/gaze |
| `ops/` | Script build AI base, tạo role chatbot, bảo trì partition, dọn Docker |
| `scripts/` | Seed tài khoản dev, reset DB, chạy backend tests |

## Chạy nhanh (Full Docker)

Yêu cầu: Docker + Docker Compose v2. Nếu dùng GPU: NVIDIA driver +
`nvidia-container-toolkit`.

```bash
# 1) Tạo file env local
cp .env.example .env
#    Chỉ cần điền khối "Bắt buộc": JWT_SECRET, CHATBOT_INTERNAL_TOKEN,
#    RIVER_API_KEY... Khối R2 để trống nếu dùng volume local; các biến
#    tuning còn lại đã có default và đang được comment sẵn.

# 2) Lần đầu: build image nền torch/CUDA dùng chung cho gaze + chatbot
./ops/build_ai_base.sh

# 3) Build + chạy toàn bộ stack
docker compose up -d --build

# 4) Mở web
#    http://localhost:3000
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

Lần đăng nhập đầu bị buộc đổi mật khẩu tại `/account/change-password`.

## Cổng

| Cổng | Dịch vụ |
|---|---|
| `3000` | nginx → web (frontend + /api + /media + /gaze) |
| `8000` | gaze (debug trực tiếp) |
| `8001` | backend (Swagger: `/docs`) |
| `8002` | chatbot (debug trực tiếp) |
| `5435` | postgres |
| `6379` | redis |

## Lệnh thường dùng

```bash
# Xem trạng thái
docker compose ps

# Log
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f nginx

# Sửa code backend/frontend → build lại service tương ứng
docker compose up -d --build backend
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

Service `migrate` tự chạy mỗi lần `docker compose up`. Runner `db/migrate.sh`:

- Ghi file đã áp vào bảng `schema_migrations`.
- Chỉ chạy file chưa áp.
- Từ chối chạy nếu file đã áp bị sửa nội dung.

Chạy tay:

```bash
docker compose run --rm migrate
```

Reset DB local (giữ weights):

```bash
./scripts/reset_db.sh
```

Quy tắc: **không sửa file migration đã áp** — thêm file mới (`025_...`).

## Chatbot RAG

Sau khi migrations chạy, tạo role DB hạn chế cho chatbot:

```bash
./ops/create_chatbot_role.sh
```

- Retrieval chỉ trong đúng `course_id`; hybrid BM25 (Postgres FTS) + vector
  (pgvector HNSW), fuse bằng RRF.
- Model: DeepSeek V4.1 Flash qua River AI cho router/answer/verifier/VLM;
  embedding local `Qwen3-Embedding-0.6B` (1024 chiều).
- Citation: mỗi claim về môn học phải có `[n]`; verifier kiểm tra evidence quote.
- Streaming SSE: `status → citations → token → done`.

## Gaze

- Calibration 16 điểm → train model `.ubj` theo phiên → lưu vào
  `calibration_params` (một bản active / user+device).
- WebSocket `/session/{sid}/stream` (qua nginx `/gaze/...`).
- Không có GPU: đặt `DEVICE=cpu` trong `.env`, bỏ `gpus: all` ở service `gaze`
  trong `docker-compose.yml`; chatbot đặt `EMBEDDING_DEVICE=cpu` và bỏ `gpus: all`.

## Tests & lint

```bash
# Backend (cần postgres + DB test)
./scripts/test_backend.sh -v

# Frontend
cd frontend && npm run lint && npm run typecheck && npm test

# Chatbot
cd services/chatbot && .venv/bin/python -m pytest tests -q

# Gaze
cd services/gaze && python -m pytest tests -q

# Ruff
ruff check backend services/gaze
```

Tạo DB test một lần:

```bash
docker compose exec -T postgres psql -U postgres -c "CREATE DATABASE eyetracking_test;"
docker compose run --rm -e PGDATABASE=eyetracking_test migrate
```

## Bảo trì partition

Migration `003` tạo partition cho 12 tháng đầu. Khi cần tạo thêm:

```bash
docker compose exec -T postgres psql -U postgres -d eyetracking \
  -c "SELECT create_gaze_partitions(3);"
```

## Dọn dung lượng Docker

```bash
./ops/docker_cleanup.sh   # chỉ prune image/build cache, KHÔNG đụng volume

# Xóa image GHCR cũ (nếu còn từ trước khi chuyển sang local)
docker image rm ghcr.io/manh1504/eyelearning-{backend,frontend,nginx,migrations,gaze,chatbot,ai-base}:latest
```

## Ghi chú

- `.env` chứa secret và đã được gitignore — không commit.
- `frontend/.env.local` trỏ backend/gaze local:
  `API_INTERNAL_URL=http://localhost:8001`, `GAZE_INTERNAL_URL=http://localhost:8000`.
- Nếu login không giữ phiên trên `http://localhost`: đặt `COOKIE_SECURE=false`
  trong `.env` rồi `docker compose up -d --build backend`.
- Nếu `npm run dev` báo cổng 3000 đang dùng: `docker compose stop nginx`.
