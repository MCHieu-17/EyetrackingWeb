# Dev local — Full Docker

Hướng dẫn chi tiết để chạy và sửa code với stack Docker local. Tóm tắt nhanh xem
`README.md`.

> Repo này **không dùng CI/CD, GHCR, Cloudflare Tunnel hay Portainer**. Mọi image
> được build từ source trên máy.

## 1. Chuẩn bị (một lần)

```bash
cp .env.example .env
# Chỉ cần điền khối "Bắt buộc": JWT_SECRET, CHATBOT_INTERNAL_TOKEN,
# RIVER_API_KEY... Khối R2 để trống nếu dùng volume local; các biến
# tuning còn lại đã có default và đang được comment sẵn.
```

Yêu cầu:
- Docker + Docker Compose v2.
- GPU (tuỳ chọn): NVIDIA driver + `nvidia-container-toolkit`.
- `psql` trên host chỉ cần nếu bạn muốn chạy script ngoài Docker; các script
  trong repo đã chuyển sang `docker compose exec`.

## 2. Build image nền AI (một lần, hoặc khi `docker/ai-base/**` đổi)

```bash
./ops/build_ai_base.sh
```

Base chứa torch/torchvision CUDA 12.4 dùng chung cho `gaze` + `chatbot`
(`eyelearning-ai-base:latest`). Không build base trước thì 2 service này sẽ lỗi
`FROM eyelearning-ai-base:latest`.

## 3. Chạy toàn bộ stack

```bash
docker compose up -d --build
```

Lần đầu sẽ build:
- `eyelearning-migrations:local`
- `eyelearning-backend:local`
- `eyelearning-frontend:local`
- `eyelearning-nginx:local`
- `eyelearning-gaze:local`
- `eyelearning-chatbot:local`

Sau đó:

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f gaze
docker compose logs -f chatbot
```

Mở <http://localhost:3000>. Backend Swagger: <http://localhost:8001/docs>.

## 4. Seed tài khoản dev

```bash
./scripts/seed_dev.sh
```

Mật khẩu chung: `Password123!`. Lần đầu đăng nhập bắt buộc đổi mật khẩu.

## 5. Tạo role DB cho chatbot

Sau khi migrations đã áp:

```bash
./ops/create_chatbot_role.sh
```

Script chạy `psql` trong container `postgres`, không cần cài psql trên host.

## 6. Sửa code thì làm gì?

| Bạn sửa | Lệnh |
|---|---|
| `backend/app/**` | `docker compose up -d --build backend` |
| `backend/requirements*.txt` | `docker compose up -d --build backend` |
| `frontend/app/**`, `components/**`, `lib/**`, `hooks/**` | `docker compose up -d --build frontend` |
| `frontend/package.json` | `docker compose up -d --build frontend` |
| `frontend/next.config.ts` | `docker compose up -d --build frontend` |
| `nginx/default.conf` | `docker compose up -d --build nginx` |
| `services/gaze/**` | `docker compose up -d --build gaze` |
| `services/chatbot/**` | `docker compose up -d --build chatbot` |
| `db/migrations/**`, `db/migrate.sh` | `docker compose up -d --build migrate` rồi `docker compose run --rm migrate` |
| `.env` | `docker compose up -d --build backend chatbot` |
| `docker/ai-base/**` | `./ops/build_ai_base.sh` rồi `docker compose up -d --build gaze chatbot` |

> Docker không có hot reload. Nếu muốn sửa là thấy ngay, xem mục 10.

### Dev không có camera

Mỗi khóa học có công tắc **“Bắt buộc hiệu chỉnh điểm nhìn”** (tab **Cài đặt**
của workspace khóa học):

1. Tắt công tắc cho khóa đang dev.
2. Sinh viên vào khóa sẽ **vào thẳng trang học**, không qua preflight.
3. Camera không bật và gaze **không được ghi** cho khóa đó — kể cả khi tài khoản
   đã có calibration cũ.
4. Bật lại khi cần test gaze/heatmap/analytics.

Mặc định công tắc **bật** để giữ hành vi cũ. Khóa cũ không cần migration dữ liệu.

## 7. Migrations

Tự động: service `migrate` chạy mỗi lần `docker compose up`.

Chạy tay:

```bash
docker compose run --rm migrate
```

Xem file đã áp:

```bash
docker compose exec -T postgres psql -U postgres -d eyetracking \
  -c "SELECT filename, applied_at FROM schema_migrations ORDER BY filename;"
```

Reset DB local (giữ weights gaze/chatbot):

```bash
./scripts/reset_db.sh
```

Quy tắc: **không sửa file migration đã áp** — thêm file mới (`025_...`).

## 8. Bảo trì partition

`gaze_events` và `gaze_raw_samples` đều partition theo tháng. **Không xoá
partition cũ** — dữ liệu raw được giữ để phân tích lại.

```bash
./scripts/create_partitions.sh        # tạo thêm 12 tháng
./scripts/create_partitions.sh 24     # hoặc chỉ định số tháng
```

## 8.1. Gaze RAW + AOI

- `GAZE_RAW_HZ` (mặc định `15`) quyết định tần số lưu `gaze_raw_samples`.
  `0` = lưu tất cả sample client gửi.
- Viewport lúc lấy mẫu **phải bằng** viewport lúc calibration. Nếu bấm F11/zoom
  làm `innerWidth/innerHeight` đổi, reader dừng ghi gaze và yêu cầu hiệu chỉnh lại.
- AOI định nghĩa ở tab **Vùng phân tích** của workspace khóa học. AOI áp dụng
  toàn hệ thống; mỗi vùng gắn với `data-aoi` trên DOM.
- Sau khi thêm/sửa AOI, bấm **Tính lại AOI hits** để rebuild `gaze_aoi_hits`
  cho khóa học.
- Chat là panel dock bên phải ở desktop `xl` (>=1280px), rộng
  `clamp(240px, 18vw, 400px)`. Mở/đóng chat tạo layout key mới
  (`reader-chat` / `quiz-chat`) và snapshot AOI mới; không có animation width
  để tránh chụp snapshot giữa lúc chuyển layout.

## 9. Tests & lint

```bash
# Backend
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

## 10. Tuỳ chọn — hot reload trên host

Nếu không muốn build lại Docker mỗi lần sửa backend/frontend:

```bash
# Hạ tầng + AI trong Docker
docker compose up -d postgres redis migrate gaze chatbot

# Terminal 1 — backend
cd backend
.venv/bin/python -m uvicorn app.main:app --reload --port 8001

# Terminal 2 — frontend
cd frontend
npm run dev
```

Khi đó web ở <http://localhost:3000> (Next.js dev), backend ở `:8001`, gaze ở
`:8000`, chatbot ở `:8002`. Nhớ `docker compose stop nginx` nếu nginx đang giữ
cổng 3000.

## 11. Xử lý sự cố

| Lỗi | Cách xử lý |
|---|---|
| `FROM eyelearning-ai-base:latest` không tìm thấy | Chạy `./ops/build_ai_base.sh` trước |
| `gpus: all` lỗi / không có GPU | Bỏ `gpus: all` ở `gaze`/`chatbot`, đặt `DEVICE=cpu`, `EMBEDDING_DEVICE=cpu` |
| Cổng 3000 đang dùng | `docker compose stop nginx` hoặc dừng process đang giữ cổng |
| Cổng 8001/8000/8002 đang dùng | `ss -ltnp \| grep -E '8000\|8001\|8002'` rồi dừng process |
| Login không giữ phiên | `.env` phải có `COOKIE_SECURE=false`, rebuild backend |
| Backend `connection refused` tới DB | `docker compose ps` — postgres chưa healthy |
| Migration lỗi | `docker logs eyetracking-migrate`; sửa file mới, không sửa file đã áp |
| Chatbot chưa `/ready` | Chờ tải weights; `docker compose logs -f chatbot` |
| Gaze chưa `/ready` | Chờ tải weights + load model; `docker compose logs -f gaze` |
| Ảnh R2 trả 403 `error code: 1010` khi test bằng Python `urllib` | Cloudflare chặn User-Agent lạ; dùng `curl`/browser hoặc `httpx`. App dùng browser/httpx nên không ảnh hưởng |
| Ảnh R2 trả 403 với mọi User-Agent | Bật Public Access cho bucket trong Cloudflare Dashboard hoặc dùng custom domain; kiểm tra `R2_PUBLIC_URL` khớp bucket |
| Hết dung lượng Docker | `./ops/docker_cleanup.sh` (không xóa volume) |

## 12. Dừng / reset

```bash
docker compose stop          # dừng, giữ dữ liệu
docker compose down          # xóa container, giữ volume
docker compose down -v       # XÓA volume — mất DB + weights
```

## 13. Cấu trúc image local

| Image | Build từ |
|---|---|
| `eyelearning-ai-base:latest` | `docker/ai-base/` |
| `eyelearning-migrations:local` | `Dockerfile.migrations` |
| `eyelearning-backend:local` | `backend/` |
| `eyelearning-frontend:local` | `frontend/` |
| `eyelearning-nginx:local` | `nginx/` |
| `eyelearning-gaze:local` | `services/gaze/` |
| `eyelearning-chatbot:local` | `services/chatbot/` |
