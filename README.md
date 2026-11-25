# START — Khởi động Eyetracking


## 1. Giới thiệu

**Eyetracking** là nền tảng học trực tuyến có theo dõi hướng nhìn.
Giáo viên soạn khóa học, bài giảng và quiz; học viên học slide PDF qua trình
duyệt, webcam gửi dữ liệu gaze về hệ thống. Backend lưu gaze thô, worker quy
đổi sang tọa độ slide/AOI và tính metrics để giáo viên phân tích.

### Người dùng và chức năng chính

| Vai trò | Chức năng |
|---|---|
| Giáo viên | Tạo khóa/chương/bài, upload PDF/PPTX/PPT/ODP, soạn quiz, chỉnh AOI, publish, xem thống kê gaze |
| Học viên | Học slide PDF, làm quiz, chat với trợ lý RAG, calibration webcam và theo dõi hướng nhìn |
| Admin | Quản lý người dùng, xem/truy vấn CSDL ở chế độ chỉ đọc |
| Khách | Trải nghiệm nhanh tại `/try` |

### Thành phần chính

```text
Browser → nginx :3000
  /api, /media → backend :8001
  /gaze        → gaze :8000
  /*           → frontend :3000

backend          → PostgreSQL + Redis
backend          → chatbot :8000 (internal token)
worker           → background_jobs(analyze_lesson)
content-worker   → background_jobs(import_slides)
embedding-worker → background_jobs(index_slides)
```

| Thành phần | Vai trò |
|---|---|
| `frontend/` | Next.js App Router: giao diện học viên, giáo viên, admin |
| `backend/` | FastAPI API, worker phân tích, content-worker, embedding-worker |
| `services/gaze/` | FaceLandmarker ONNX + UniGaze ONNX + WebSocket calibration (mặc định cần GPU); báo cáo nghiên cứu ở [`docs/gaze/`](docs/gaze/README.md) |
| `services/chatbot/` | RAG: ingest slide, hybrid retrieval, gọi LLM/VLM qua endpoint OpenAI-compatible |
| `db/` | Baseline PostgreSQL generation 13, 24 bảng lõi |
| `nginx/` | Reverse proxy local |
| `scripts/` | Seed, reset, backup, smoke test, kiểm tra |

Database dùng **schema generation 13**, không versioning nội dung. Sửa nội dung
đã publish có hiệu lực ngay; quiz đã làm giữ đề trong `quiz_attempts.quiz_snapshot`.

### Chạy nhanh

Khi `.env` đã cấu hình đúng và máy có GPU:

```bash
docker compose up -d --build
# Đợi service migrate Exited (0), backend và chatbot healthy
./scripts/seed_dev.sh
./scripts/smoke.sh
```

Mở <http://localhost:3000>. Nếu chưa có `.env`, máy không có GPU hoặc muốn hiểu
từng bước, đọc tiếp các mục bên dưới.

### Cổng truy cập mặc định

Các cổng debug chỉ bind loopback (`127.0.0.1`), tức là chỉ truy cập từ máy đang chạy.

| Cổng | Dịch vụ |
|---|---|
| `3000` | Website qua nginx, đồng thời `/api`, `/media`, `/gaze` |
| `8001` | Backend API — Swagger tại `/docs` |
| `8002` | Chatbot service |
| `5435` | PostgreSQL |
| `6379` | Redis |

Gaze không publish cổng ra host vì có thể chạy nhiều replica. Truy cập qua nginx tại
`/gaze/...` hoặc debug bằng `docker compose exec gaze ...`.

## 2. Chuẩn bị môi trường

### 2.1 Phần mềm bắt buộc

- Docker Engine (khuyến nghị 24+)
- Docker Compose v2 (`docker compose`, không phải `docker-compose` cũ)
- Git và Bash
- `curl` (smoke test), `openssl` (tạo secret), `ss` (kiểm tra cổng)

Kiểm tra:

```bash
docker --version
docker compose version
```

### 2.2 Tài nguyên khuyến nghị

- **RAM:** 16 GB trở lên. Stack có nhiều service; máy yếu nên giảm replica.
- **CPU:** 4 lõi trở lên.
- **Ổ đĩa:** khoảng 30 GB trống trở lên cho image, model weights, DB và media.
- **Mạng:** cần Internet cho lần build đầu và tải model weights.

Các image/model không nằm trong Git. Lần chạy đầu sẽ build image và tải weights
vào Docker volume, nên có thể mất **10–30 phút** tùy máy và đường truyền.

### 2.3 Cổng cần trống

Đảm bảo các cổng `3000`, `8001`, `8002`, `5435`, `6379` chưa bị chiếm:

```bash
ss -ltnp | grep -E ':(3000|8001|8002|5435|6379)\b'
```

Nếu có dịch vụ khác đang dùng, dừng dịch vụ đó hoặc đổi port mapping trong
`docker-compose.yml` (và cập nhật URL tương ứng trong `.env`).

### 2.4 GPU (tùy chọn)

Mặc định service `gaze` dùng `gpus: all`, cần:

- NVIDIA driver
- `nvidia-container-toolkit`

Kiểm tra nhanh:

```bash
nvidia-smi
```

Nếu **không có GPU**, xem mục [7.1 Chạy không có GPU](#71-chạy-không-có-gpu)
trước khi khởi động lần đầu. Gaze vẫn chạy bằng CPU nhưng rất chậm, không phù
hợp để dùng thật.

## 3. Cấu hình `.env`

Toàn bộ stack đọc file `.env` ở thư mục gốc repo. `.env` chứa secret nên
**không commit** và không chia sẻ công khai.

### 3.1 Tạo file cấu hình

Nếu chưa có `.env`:

```bash
[ -f .env ] || cp .env.example .env
```

Mở `.env` và điền các giá trị bắt buộc. Có thể sinh secret bằng:

```bash
openssl rand -hex 32
```

Chạy lệnh trên nhiều lần để lấy các secret khác nhau.

### 3.2 Các biến quan trọng

| Biến | Ghi chú |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Tài khoản/tên DB PostgreSQL |
| `DATABASE_URL_DOCKER` | DSN backend dùng trong Docker; **mật khẩu phải khớp `POSTGRES_PASSWORD`** |
| `DATABASE_URL` | DSN khi chạy backend trực tiếp trên host; dùng `localhost:5435` |
| `JWT_SECRET` | Secret ký JWT, chuỗi dài ngẫu nhiên |
| `CORS_ORIGINS` | Với local: `http://localhost:3000` |
| `COOKIE_SECURE` | Local chạy HTTP: **phải là `false`** |
| `CHATBOT_INTERNAL_TOKEN` | Token backend ↔ chatbot, chuỗi dài ngẫu nhiên |
| `CHATBOT_DB_PASSWORD` | Mật khẩu role `chatbot_reader` |
| `CHATBOT_DATABASE_URL_DOCKER` | DSN chatbot; **mật khẩu phải khớp `CHATBOT_DB_PASSWORD`** |
| `ADMIN_DB_PASSWORD` | Mật khẩu role `admin_reader` |
| `ADMIN_DATABASE_URL_DOCKER` | DSN admin read-only; **mật khẩu phải khớp `ADMIN_DB_PASSWORD`** |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `VLM_MODEL` | Endpoint/model LLM/VLM cho chatbot (OpenAI-compatible) |
| `DEVICE`, `UNIGAZE_MODEL` | Model gaze chạy local; **bắt buộc**, không có default trong code/compose |
| `EMBEDDING_NAME`, `EMBEDDING_DIM`, `EMBEDDING_MODEL_PATH`, `EMBEDDING_DEVICE`, `EMBEDDING_LOCAL_FILES_ONLY`, `EMBEDDING_HF_REPO` | Model embedding chatbot; **bắt buộc**, không có default |
| `FRONTEND_REPLICAS`, `GAZE_REPLICAS`, `WORKER_REPLICAS` | Số replica; máy cá nhân nên đặt `1` |
| `CONTENT_VIEW_MIN_DWELL_MS` | Ngưỡng phân loại lượt xem đủ ngưỡng; mặc định `1000`, không ẩn lượt ngắn |
| `GAZE_FPS` | Frame/giây gaze, `1..60` (khuyến nghị `6..30`); backend trả qua `/api/config`, frontend không cần rebuild |

Ví dụ các dòng cần đồng bộ (thay `<secret-N>` bằng giá trị thật):

```env
POSTGRES_PASSWORD=<secret-1>
DATABASE_URL_DOCKER=postgresql+asyncpg://postgres:<secret-1>@postgres:5432/eyetracking

JWT_SECRET=<secret-2>
CHATBOT_INTERNAL_TOKEN=<secret-3>

CHATBOT_DB_PASSWORD=<secret-4>
CHATBOT_DATABASE_URL_DOCKER=postgresql://chatbot_reader:<secret-4>@postgres:5432/eyetracking

ADMIN_DB_PASSWORD=<secret-5>
ADMIN_DATABASE_URL_DOCKER=postgresql+asyncpg://admin_reader:<secret-5>@postgres:5432/eyetracking
```

> Dùng secret dạng hex để tránh ký tự đặc biệt (`@`, `:`, `/`) làm hỏng DSN.

Nếu chạy backend/frontend trực tiếp trên host, cập nhật thêm:

```env
DATABASE_URL=postgresql+asyncpg://postgres:<secret-1>@localhost:5435/eyetracking
ADMIN_DB_URL=postgresql+asyncpg://admin_reader:<secret-5>@localhost:5435/eyetracking
```

Các biến model local (`DEVICE`, `UNIGAZE_MODEL`, `EMBEDDING_*`) **phải** đặt
tường minh trong `.env`; không có default trong code/compose. Các biến còn lại
có thể giữ mặc định trong `.env.example`.

### 3.3 Cấu hình tùy chọn

**Đăng nhập sinh viên bằng email + OTP** — không cần Azure App Registration
hay quyền Microsoft Entra admin. Điền SMTP của tài khoản gửi mail:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-sender@gmail.com
SMTP_PASS=app-password
SMTP_FROM=              # trống → dùng SMTP_USER
SMTP_FROM_NAME=Eyetracking
SMTP_REPLY_TO=          # trống → dùng địa chỉ From
SMTP_USE_SSL=false
SMTP_STARTTLS=true
OTP_TTL_SECONDS=900
OTP_ALLOWED_DOMAINS=st.neu.edu.vn
OTP_STUDENT_ID_PATTERN=^\d{8}$
```

Sinh viên bấm “Đăng nhập với email Outlook trường”, nhập
`12345678@st.neu.edu.vn`, nhận mã 6 số qua hộp thư Outlook và xác nhận. Tài khoản
mới được tạo với role `student`; email đã tồn tại giữ nguyên role hiện có.
Không dùng `MICROSOFT_CLIENT_ID/SECRET/TENANT_ID` nữa.

Nếu chưa cấu hình SMTP, backend trả lỗi “chưa cấu hình gửi email”; dev có thể
bật `OTP_DEV_ECHO=true` để in mã ra log backend. Khi thử với hộp thư Outlook
trường, nhớ kiểm tra cả **Thư rác/Quarantine** ở lần gửi đầu; Gmail cá nhân
gửi tới Microsoft 365 có thể bị chuyển vào đó. Lỗi `550 5.4.1 Recipient address
rejected: Access denied` là địa chỉ sinh viên không tồn tại, không phải lỗi
SMTP.

**Ngưỡng lượt xem / Trực quan hoá** — mặc định mọi lượt xem đều được hiển thị,
kể cả lượt ngắn hoặc không có mẫu gaze:

```env
CONTENT_VIEW_MIN_DWELL_MS=1000
```

Giá trị này chỉ dùng để gắn nhãn “Ngắn <1s” và bật bộ lọc “Chỉ lượt >= ngưỡng”
trong tab Trực quan hoá; không ẩn dữ liệu mặc định. Đổi giá trị cần recreate
backend: `docker compose up -d backend`.

Tab Tổng hợp mặc định lọc **90 ngày gần nhất** (hiện trong ô “Từ ngày”/“Đến
ngày”); xoá cả hai ô để xem toàn bộ lịch sử. Heatmap theo slide dùng cùng cửa
sổ thời gian này.

**Lưu trữ slide** — mặc định dùng volume local:

```env
STORAGE_PROVIDER=local
```

Nếu dùng Cloudflare R2, đặt `STORAGE_PROVIDER=r2` và điền **đủ cả 5** biến
`R2_ACCOUNT_ID`, `R2_BUCKET_NAME`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
`R2_PUBLIC_URL`. Thiếu một biến, backend sẽ báo lỗi cấu hình R2.

**Chatbot RAG** — cần `LLM_BASE_URL` và `LLM_MODEL` (cùng các biến `LLM_*`/
`VLM_*` liên quan; `LLM_API_KEY` nếu endpoint yêu cầu auth). Nếu không có quyền
gọi endpoint LLM, các chức năng khác vẫn chạy nhưng chat và ingest slide sẽ lỗi.

## 4. Khởi động lần đầu

> Nếu máy không có GPU, làm mục [7.1](#71-chạy-không-có-gpu) trước.

### 4.1 Build và chạy stack

Từ thư mục gốc repo:

```bash
docker compose up -d --build
```

Lần đầu, Compose sẽ:

1. Build image frontend, backend, chatbot, gaze, nginx và migration.
2. Khởi động PostgreSQL + Redis.
3. Chạy service một lần `migrate` để áp baseline generation 12 + nâng cấp generation 13.
4. Khởi động backend, các worker, chatbot, gaze, frontend và nginx.
5. `gaze-export` tải UniGaze safetensors và export ONNX (chạy một lần); gaze-export cũng convert FaceLandmarker sang ONNX; chatbot tải Qwen3-Embedding weights vào
   volume. Bước này có thể mất vài phút.

### 4.2 Theo dõi trạng thái

```bash
docker compose ps -a
docker compose logs -f migrate
```

- `eyetracking-migrate` **Exited (0)** là bình thường: đây là service chạy một lần.
- `postgres`, `redis`, `backend`, `chatbot` cần chuyển sang `healthy`.
- `frontend`, `gaze`, `worker`, `content-worker`, `embedding-worker`, `nginx`
  cần ở trạng thái `running`.
- `chatbot` và `gaze` có `start_period` dài vì phải tải model; đợi thêm vài
  phút trước khi kết luận lỗi.

Xem log khi có service chưa lên:

```bash
docker compose logs -f backend
docker compose logs -f chatbot
docker compose logs -f gaze
```

### 4.3 Seed tài khoản development

Sau khi migration hoàn tất và PostgreSQL đang chạy:

```bash
./scripts/seed_dev.sh
```

Script tạo 3 tài khoản mẫu nếu chưa tồn tại, **không ghi đè mật khẩu** của tài
khoản đã có. Chạy lại nhiều lần vẫn an toàn.

| Email | Mật khẩu | Role |
|---|---|---|
| `admin@school.edu.vn` | `Password123!` | admin |
| `teacher@school.edu.vn` | `Password123!` | teacher |
| `student@school.edu.vn` | `Password123!` | student |

Đăng ký bằng email/password đã tắt. Sinh viên tạo tài khoản bằng email trường +
OTP và mặc định có role student. Giáo viên/admin dùng tài khoản được cấp mật
khẩu hoặc seed development.

### 4.4 Mở website

Truy cập:

- Website: <http://localhost:3000>
- Swagger backend: <http://localhost:8001/docs>
- Kiểm tra nginx: <http://localhost:3000/nginx-health>

Nếu dùng webcam/calibration, hãy mở bằng `localhost` hoặc `127.0.0.1`. Trình
duyệt chỉ cho phép webcam trên secure context (localhost hoặc HTTPS).

### 4.5 Smoke test

Chạy kiểm tra nhanh sau khi stack đã lên:

```bash
./scripts/smoke.sh
```

Script kiểm tra lần lượt nginx, backend, gaze qua nginx và chatbot. Kết thúc bằng
`[smoke] OK` là stack cơ bản đã sẵn sàng.

Kiểm tra thủ công:

| URL | Ý nghĩa |
|---|---|
| `http://localhost:8001/health` | Backend liveness |
| `http://localhost:8002/health` | Chatbot liveness |
| `http://localhost:8002/ready` | Chatbot readiness (DB + model) |
| `http://localhost:3000/gaze/health` | Gaze liveness qua nginx |
| `http://localhost:3000/gaze/ready` | Gaze readiness (model đã load) |

## 5. Sử dụng hằng ngày

### 5.1 Khởi động và tắt

```bash
# Khởi động lại stack đã build, không build lại
docker compose up -d

# Xem trạng thái
docker compose ps

# Dừng container, giữ nguyên volume/dữ liệu
docker compose stop

# Xóa container, giữ nguyên volume/dữ liệu
docker compose down
```

> `docker compose down -v` sẽ **xóa toàn bộ volume**: database, media, weights
> gaze/chatbot và Redis. Chỉ dùng khi thật sự muốn reset sạch. Bình thường dùng
> `down` hoặc `./scripts/reset_db.sh`.

### 5.2 Xem log

```bash
docker compose logs -f               # tất cả service
docker compose logs -f backend
docker compose logs -f worker
docker compose logs -f content-worker
docker compose logs -f embedding-worker
```

### 5.3 Build lại sau khi sửa code

```bash
# Backend API + worker phân tích + embedding worker dùng chung image backend
docker compose up -d --build backend worker embedding-worker

# Content worker có image riêng (LibreOffice)
docker compose up -d --build content-worker

# Frontend
docker compose up -d --build frontend

# Toàn bộ stack
docker compose up -d --build
```

Sau khi sửa `.env`, recreate các service bị ảnh hưởng:

```bash
docker compose up -d --force-recreate backend worker content-worker embedding-worker
```

`docker compose restart` chỉ khởi động lại process, **không** áp dụng biến môi
trường mới và không build lại image.

### 5.4 Dùng thử các khu vực chính

| Đường dẫn | Khu vực |
|---|---|
| `/` | Landing page |
| `/account/login` | Đăng nhập |
| `/teacher` | Danh sách khóa của giáo viên |
| `/teacher/courses/{id}` | Workspace giáo viên: nội dung, thông tin, cài đặt, học viên, AOI |
| `/student` | Dashboard học viên |
| `/student/courses/{id}` | Học slide/quiz |
| `/student/courses/{id}/calibrate` | Calibration webcam |
| `/admin` | Quản trị người dùng |
| `/admin/database` | Truy vấn CSDL read-only |
| `/try` | Trải nghiệm khách |

Luồng thử nhanh với giáo viên:

1. Đăng nhập `teacher@school.edu.vn`.
2. Vào `/teacher`, tạo khóa học.
3. Tạo chương, bài giảng; upload PDF/PPTX/PPT/ODP.
4. Soạn quiz và chỉnh AOI nếu cần.
5. Publish khóa học. Publish sẽ validate chương/bài, slide đã index xong và
   quiz hợp lệ.

> Slide chỉ publish được khi `embedding-worker` đã index xong, mà bước này cần
> chatbot `/ready`. Nếu upload xong nhưng mãi ở trạng thái pending, xem log
> `content-worker`, `embedding-worker` và chatbot.

Học viên cần được giáo viên ghi danh vào khóa trước khi thấy khóa trong
`/student`.

### 5.5 Triển khai production bằng Portainer

Stack production dùng image build sẵn, không build trên server:

- GitHub Actions build 8 image (thêm `gaze-export`) → GHCR.
- Portainer chỉ pull image và chạy `deploy/portainer/docker-compose.yml`.
- `cloudflared` nằm trong stack, nhận traffic Cloudflare Tunnel và trỏ tới
  `http://nginx:80`.
- Không publish port host; DB/Redis không lộ ra ngoài.

Hướng dẫn đầy đủ, env mẫu, Cloudflare Tunnel, backup/restore và rollback:
[`deploy/portainer/README.md`](deploy/portainer/README.md).

## 6. Seed, reset và backup dữ liệu

### 6.1 Seed lại tài khoản dev

```bash
./scripts/seed_dev.sh
```

Có thể chạy bất cứ lúc nào khi PostgreSQL đang chạy. Không ghi đè mật khẩu hiện
có.

### 6.2 Reset database development

Reset có guard, mặc định chỉ **preview** và không thay đổi gì:

```bash
./scripts/reset_db.sh
```

Áp dụng thật (bắt buộc `--database` và `--confirm-reset` trùng nhau):

```bash
./scripts/backup.sh

./scripts/reset_db.sh --apply \
  --database eyetracking \
  --confirm-reset eyetracking \
  --seed-dev
```

- `--database` phải khớp `POSTGRES_DB` (mặc định `eyetracking`).
- `--seed-dev` tùy chọn; nếu bỏ qua, chạy `./scripts/seed_dev.sh` sau reset.
- Script sẽ dừng runtime, drop/recreate database, chạy baseline + grants, seed
  (nếu có) rồi khởi động lại các service đang chạy trước đó.
- Nếu stack đang tắt hoàn toàn, chạy `docker compose up -d` sau khi reset.
- Reset **xóa dữ liệu** trong database đích. Backup trước nếu cần giữ dữ liệu.

### 6.3 Backup và phục hồi

```bash
# Tạo backup vào backups/
./scripts/backup.sh

# Phục hồi (hỏi xác nhận)
./scripts/backup.sh --restore backups/eyelearning-YYYYmmdd-HHMMSS.dump
```

Nên dừng backend và worker trước khi restore để tránh connection đang giữ object:

```bash
docker compose stop backend worker content-worker
```

Chi tiết xem [`docs/OPERATIONS.md`](docs/OPERATIONS.md).

## 7. Cấu hình thường gặp

### 7.1 Chạy không có GPU

Mặc định gaze yêu cầu NVIDIA GPU. Nếu máy không có GPU:

1. Trong `.env`, đặt:

   ```env
   DEVICE=cpu
   INFERENCE_PRECISION=fp32
   GAZE_GPU_BATCH=1
   FRONTEND_REPLICAS=1
   GAZE_REPLICAS=1
   WORKER_REPLICAS=1
   ```

2. Mở `docker-compose.yml`, tìm service `gaze` và **xóa dòng**:

   ```yaml
   gpus: all
   ```

3. Khởi động lại:

   ```bash
   # Nếu stack chưa chạy lần nào
   docker compose up -d --build

   # Nếu chỉ muốn áp dụng thay đổi cho gaze/nginx
   docker compose up -d --build gaze nginx
   ```

Gaze CPU vẫn chạy nhưng suy luận rất chậm, chỉ phù hợp để kiểm tra giao diện
hoặc phát triển. Không nên dùng cho lớp học thật.

### 7.2 Máy yếu, muốn tiết kiệm RAM

Đặt trong `.env`:

```env
FRONTEND_REPLICAS=1
GAZE_REPLICAS=1
WORKER_REPLICAS=1
```

Sau đó:

```bash
docker compose up -d --force-recreate frontend gaze worker
```

Không đặt replica về `0` cho các service mà nginx/backend phụ thuộc.

### 7.3 Đổi mật khẩu PostgreSQL

Nếu database **chưa từng khởi tạo** (chưa có volume `pgdata`), chỉ cần sửa
`.env` trước lần `up` đầu tiên:

- `POSTGRES_PASSWORD`
- `DATABASE_URL_DOCKER`
- `DATABASE_URL` (nếu chạy backend trên host)

Nếu database **đã khởi tạo**, đổi `POSTGRES_PASSWORD` trong `.env` không tự đổi
mật khẩu role trong volume. Cần đổi trong PostgreSQL trước:

```bash
docker compose exec postgres psql -U postgres -d postgres \
  -c "ALTER USER postgres WITH PASSWORD '<new-password>';"
```

Sau đó cập nhật `POSTGRES_PASSWORD` và các DSN trong `.env`, rồi recreate các
service liên quan:

```bash
docker compose up -d --force-recreate postgres migrate backend worker content-worker embedding-worker
```

Nếu chỉ đổi mật khẩu trong `POSTGRES_PASSWORD` mà quên DSN, backend sẽ báo lỗi
kết nối database.

### 7.4 Chatbot không dùng được

Kiểm tra:

```bash
docker compose logs -f chatbot
curl -fsS http://localhost:8002/ready
```

Các nguyên nhân thường gặp:

- Chưa tải xong embedding weights trong lần chạy đầu.
- `LLM_BASE_URL`/`LLM_API_KEY` sai hoặc không truy cập được endpoint LLM/VLM.
- `CHATBOT_DB_PASSWORD` không khớp `CHATBOT_DATABASE_URL_DOCKER`.
- Role `chatbot_reader` chưa được tạo/cấp lại quyền.

Cấp lại role chatbot (migrate tự áp role, idempotent):

```bash
docker compose run --rm migrate
```

### 7.5 Dùng R2 thay vì lưu local

Điền đủ 5 biến `R2_*` trong `.env`, đặt:

```env
STORAGE_PROVIDER=r2
```

Sau đó recreate backend, content-worker và chatbot:

```bash
docker compose up -d --force-recreate backend content-worker chatbot
```

Nếu không dùng R2, đặt `STORAGE_PROVIDER=local` và để trống toàn bộ `R2_*`.

## 8. Kiểm tra và test

### 8.1 Kiểm tra runtime

```bash
./scripts/smoke.sh
```

### 8.2 Kiểm tra chất lượng code (dành cho dev)

Các lệnh này cần cài dependency trên host (Python venv, `npm install`):

```bash
make check          # Ruff, ESLint, TypeScript, compose config
make check-full     # thêm knip + frontend build
```

Kiểm tra migration:

```bash
./scripts/test_migrations.sh
```

Test tự động chia 2 nhóm:

```bash
make test-fast      # backend + gaze + chatbot, mock model/LLM, DB/Redis test
make test-smoke     # model thật + chatbot RAG + E2E Playwright trước merge
```

Chạy riêng:

```bash
./scripts/test_backend.sh
./scripts/test_gaze.sh fast        # hoặc smoke
./scripts/test_chatbot.sh fast     # hoặc smoke
./scripts/e2e.sh                   # seed E2E + Playwright, cần stack
E2E_CHAT=1 ./scripts/e2e.sh        # thêm luồng chat thật
```

Phạm vi và quy ước test: mục 2 `AGENTS.md`.

## 9. Xử lý sự cố nhanh

| Hiện tượng | Kiểm tra / cách xử lý |
|---|---|
| `port is already allocated` | Chạy `ss -ltnp` để xem cổng đang bị chiếm; dừng dịch vụ đó hoặc đổi port mapping |
| `migrate` exit khác 0 | `docker compose logs migrate`; kiểm tra checksum migration, DB cũ hoặc sai mật khẩu |
| Backend không healthy | `docker compose ps`, log backend; kiểm tra `POSTGRES_PASSWORD` khớp DSN, PostgreSQL đã healthy |
| Đăng nhập không giữ phiên | Đặt `COOKIE_SECURE=false`, đảm bảo chỉ có **một dòng** cấu hình này; recreate backend; truy cập bằng `http://localhost:3000` |
| Chatbot chưa ready | Chờ tải weights lần đầu; xem log chatbot; kiểm tra `LLM_*`/`VLM_*`, role `chatbot_reader` |
| Gaze chưa ready | Chờ tải weights; kiểm tra NVIDIA driver/container toolkit; xem log gaze; thử `DEVICE=cpu` nếu không có GPU |
| Upload slide bị treo | `docker compose logs -f content-worker`; kiểm tra LibreOffice trong image content-worker và job `import_slides` |
| Slide không index được | `docker compose logs -f embedding-worker`; kiểm tra chatbot `/ready` và cấu hình LLM/VLM |
| Hết dung lượng Docker | `docker system df`; chạy `./scripts/docker_cleanup.sh`; **không prune volume** |
| Muốn reset sạch | Backup rồi dùng `./scripts/reset_db.sh --apply ...`; tránh `docker compose down -v` nếu chưa chắc |

Khi cần xem toàn bộ log để báo lỗi:

```bash
docker compose ps -a
docker compose logs --tail=200
```

## 10. Tài liệu liên quan

- [`README.md`](README.md) — tổng quan dự án, kiến trúc, lệnh thường dùng
- [`AGENTS.md`](AGENTS.md) — quy tắc phát triển, mô hình dữ liệu, từ điển bảng/ERD
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md) — backup, restore, bảo trì, logging
- [`backend/README.md`](backend/README.md) — API, worker, luồng backend
- [`frontend/README.md`](frontend/README.md) — cấu trúc frontend, route, gaze flow
- [`services/gaze/README.md`](services/gaze/README.md) — calibration, WebSocket, model
- [`services/chatbot/README.md`](services/chatbot/README.md) — RAG, ingest, cấu hình chatbot
- [`db/README.md`](db/README.md) — migration, seed, reset database
- [`scripts/README.md`](scripts/README.md) — toàn bộ script vận hành
