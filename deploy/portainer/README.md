# Triển khai production bằng Portainer + Cloudflare Tunnel

Tài liệu này dành cho server chỉ cho phép thao tác qua **Portainer**, không SSH.
Stack production chỉ **pull image** từ registry, không build trên server.

Kiến trúc:

```text
GitHub Actions → GHCR
                  │
Portainer stack ──┼── cloudflared ──→ nginx:80
                  │                     ├── frontend:3000
                  │                     ├── backend:8001
                  │                     └── gaze:8000
                  ├── backend → postgres / redis / chatbot
                  ├── content-worker
                  ├── worker / embedding-worker
                  └── chatbot / gaze / postgres / redis
```

---

## 1. Điều kiện server

Tối thiểu:

- Docker Engine 24+, Docker Compose v2
- Portainer 2.20+ / 2.39 LTS
- amd64
- 16 GB RAM, 4 core, 30 GB disk trống
- Khuyến nghị: 32 GB RAM, 8 core, 50 GB+
- GPU NVIDIA nếu dùng gaze thật:
  - NVIDIA driver
  - `nvidia-container-toolkit`
  - GPU ≥ 8 GB VRAM
- Outbound:
  - `ghcr.io` (hoặc registry riêng), `docker.io`
  - `*.argotunnel.com`, UDP/TCP **7844** cho cloudflared
  - `huggingface.co`, Google Drive/Storage (weights gaze/chatbot)
  - SMTP port 587 hoặc 465
  - Endpoint LLM/VLM theo `LLM_BASE_URL` (HTTPS)
  - R2 endpoint nếu dùng Cloudflare R2

Nếu server chặn 7844, thử thêm `--protocol http2` vào command cloudflared;
nếu vẫn không được, phải nhờ admin mở 7844 hoặc dùng phương án tunnel ngoài.

---

## 2. Build image

Workflow `.github/workflows/release.yml` build 7 image:

| Image | Dockerfile | Target |
|---|---|---|
| `eyelearning-backend` | `backend/Dockerfile` | `api` |
| `eyelearning-content-worker` | `backend/Dockerfile` | `content-worker` |
| `eyelearning-chatbot` | `services/chatbot/Dockerfile` | mặc định |
| `eyelearning-gaze` | `services/gaze/Dockerfile` | mặc định |
| `eyelearning-frontend` | `frontend/Dockerfile` | mặc định |
| `eyelearning-nginx` | `nginx/Dockerfile` | mặc định |
| `eyelearning-migrations` | `db/Dockerfile` | mặc định |

### Cách 1 — GitHub Actions (khuyến nghị)

```bash
git tag v1.1.1
git push origin v1.1.1
```

- Tag `v*` build **toàn bộ** image và gắn tag `v1.1.1`.
- Push `main` chỉ build image có path thay đổi, gắn `sha-...` + `latest`.
- Có thể chạy tay workflow `Release` (build toàn bộ).

Nếu `deploy/portainer/stack.env` đang dùng `IMAGE_TAG=v1.1.1`, phải push tag
`v1.1.1` và chờ workflow build xong **trước khi** deploy stack.

Sau lần push đầu, vào GitHub → Packages:

- **Public**: package Settings → Change visibility → Public.
- **Private**: thêm registry trong Portainer:
  - Registry URL: `ghcr.io`
  - Username: GitHub username
  - Password: PAT có quyền `read:packages`

### Cách 2 — build local

```bash
docker login ghcr.io
IMAGE_PREFIX=ghcr.io/mchieu-17 IMAGE_TAG=v1.1.1 ./scripts/publish_images.sh
```

Bỏ qua gaze nếu chỉ muốn build phần còn lại:

```bash
SKIP_GAZE=1 IMAGE_PREFIX=ghcr.io/mchieu-17 IMAGE_TAG=v1.1.1 ./scripts/publish_images.sh
```

---

## 3. Tạo stack trên Portainer

1. Portainer → **Stacks** → **Add stack**.
2. Name: `eyelearning-prod` (giữ nguyên tên này giữa các lần deploy).
3. Build method: **Repository**.
4. Repository URL: `https://github.com/MCHieu-17/EyetrackingWeb`
5. Branch: `main`
6. Compose path: `deploy/portainer/docker-compose.yml`
7. Environment variables:
   - Copy `deploy/portainer/stack.env.example`
   - Điền secret thật
   - Dán vào Portainer, hoặc upload file `.env` qua nút **Load variables from .env file**
   - File `deploy/portainer/stack.env` trên máy local đã được tạo từ `.env` +
     tunnel token; file này **đã gitignore**, chỉ dùng để dán vào Portainer.
   - Nên dùng **Load variables from .env file** để Compose xử lý đúng dấu cách.
     Nếu nhập tay từng biến, không thêm dấu ngoặc kép vào giá trị.
   - Các biến model local **bắt buộc**: `DEVICE`, `UNIGAZE_MODEL`,
     `EMBEDDING_NAME`, `EMBEDDING_DIM`, `EMBEDDING_MODEL_PATH`,
     `EMBEDDING_DEVICE`, `EMBEDDING_LOCAL_FILES_ONLY`, `EMBEDDING_HF_REPO`.
     Thiếu một biến → Compose báo lỗi ngay, không dùng default.
   - `GAZE_FPS` (mặc định `15`, hợp lệ `1..60`): frame/giây gaze; backend trả
     lại qua `/api/config`, gaze throttle `1000/FPS × 0.95`. Đổi giá trị chỉ cần
     **redeploy stack**, không build lại image (frontend đọc runtime).
   - LLM/VLM: `LLM_BASE_URL` và `LLM_MODEL` **bắt buộc**; `LLM_API_KEY` nếu
     endpoint cần auth. Các key cũ `NEU_*` đã được thay bằng `LLM_*`/`VLM_*`;
     đổi tên trong Portainer trước khi deploy image mới.
8. Deploy the stack.

Nếu Portainer không cho Git repository, dùng **Web editor** và dán nội dung
`deploy/portainer/docker-compose.yml`, vẫn giữ nguyên env.

### Thứ tự khởi động

```text
backup-init (exit 0)
  → postgres healthy
    → migrate (exit 0)
      → backend, content-worker, worker, embedding-worker, chatbot
        → nginx healthy
          → cloudflared
```

Lần đầu có thể mất **20–40 phút** vì pull image (gaze ~10 GB) và tải weights.

Kiểm tra trong Portainer:

- `migrate` exit code **0**
- `backend` healthy
- `nginx` healthy
- `chatbot` ready
- `gaze` ready
- `cloudflared` running

Nếu `migrate` fail, xem log `migrate`; backend sẽ không lên.

---

## 4. Cloudflare Tunnel

### Cách A — tạo tunnel mới (khuyến nghị)

1. Cloudflare Zero Trust → Networks → Tunnels → **Create a tunnel**.
2. Chọn **Cloudflared**, đặt tên `eyelearning-prod`.
3. Copy **TUNNEL_TOKEN**, đưa vào env Portainer.
4. Thêm Public Hostname tạm:
   - Subdomain: `staging-eyelearning`
   - Domain: `nmhieu17.space`
   - Service: **HTTP** → `nginx:80`
5. Deploy stack, test qua `https://staging-eyelearning.nmhieu17.space`.
6. Thêm/chuyển public hostname production:
   - `eyetracking.nmhieu17.space` → HTTP `nginx:80`
7. Stop tunnel local:
   ```bash
   systemctl --user stop cloudflared
   systemctl --user disable cloudflared
   ```

Giữ tunnel cũ + stack local ít nhất 7 ngày để rollback.

### Cách B — dùng lại tunnel hiện tại

Tunnel hiện tại đang trỏ:

```text
eyetracking.nmhieu17.space → http://localhost:3000
```

Token của tunnel hiện tại nằm trong `~/.cloudflared/tunnel.env` trên máy local;
`deploy/portainer/stack.env` đã copy token này (không commit).

Nếu muốn dùng lại:

1. Deploy stack mới trước (cloudflared kết nối nhưng chưa có traffic).
2. Vào tunnel → Public Hostname → sửa service thành `http://nginx:80`.
3. Stop cloudflared local ngay:
   ```bash
   systemctl --user stop cloudflared
   systemctl --user disable cloudflared
   ```
4. Test. Nếu lỗi, sửa service về `http://localhost:3000`, bật lại local.

Không chạy đồng thời connector local và connector production nếu ingress chỉ
trỏ được một nơi; traffic sẽ bị chia và lỗi.

### Lưu ý CORS/CSRF

Backend kiểm tra double-submit CSRF cho request ghi bằng cookie. Request
**cùng host** với request hiện tại (same-origin) luôn được chấp nhận sau khi
token khớp; chỉ request cross-origin mới phải nằm trong `CORS_ORIGINS`.

Khi staging/domain phụ có frontend gọi API khác origin, khai báo đủ hostname:

```env
CORS_ORIGINS=https://eyetracking.nmhieu17.space,https://eyetracking01.nmhieu17.space,https://staging-eyelearning.nmhieu17.space
```

Nếu frontend và API cùng public hostname (đi qua nginx), không cần thêm
hostname đó chỉ để lưu dữ liệu; vẫn nên khai báo đủ nếu có client cross-origin.
Sau cutover có thể bỏ staging rồi recreate backend.

---

## 5. Tạo tài khoản đầu tiên

Vì chọn **làm mới hoàn toàn**, không chạy `db/seed_dev_users.sql`.

Mở Portainer → Containers → container backend → **Console**, chạy:

```bash
python -m app.cli.create_admin \
  --email admin@example.com \
  --name "Quản trị viên" \
  --role admin
```

CLI sẽ hỏi mật khẩu. Tạo teacher:

```bash
python -m app.cli.create_admin \
  --email teacher@example.com \
  --name "Giáo viên" \
  --role teacher \
  --department "Khoa Công Nghệ Thông Tin"
```

Nếu email đã tồn tại và muốn cập nhật:

```bash
python -m app.cli.create_admin ... --force
```

Sinh viên tự đăng ký bằng OTP với email `@st.neu.edu.vn`.

---

## 6. Dữ liệu mới và R2

- DB mới do `migrate` tạo, schema generation 13.
- `app_metadata.db_instance_id` mới.
- Media trên R2 dùng prefix `instances/{db_instance_id}/...`.
- Object R2 của DB cũ không còn được tham chiếu; có thể xóa sau khi xác nhận.
- Nếu muốn dùng bucket R2 mới, điền lại 5 biến `R2_*` và
  `STORAGE_PROVIDER=r2`.

Nếu sau này cần chuyển dữ liệu cũ sang, xem mục backup/restore bên dưới.

---

## 7. Kiểm tra sau deploy

```bash
BASE_URL=https://eyetracking.nmhieu17.space ./scripts/smoke_remote.sh
```

Script kiểm tra:

- `/nginx-health`
- `/`
- `/account/login`
- `/gaze/health`
- `/gaze/ready` (model gaze đã load)
- `/api/me/profile` (backend sống; 401/403 vẫn OK)

Kiểm tra thủ công:

- Đăng nhập admin/teacher.
- OTP sinh viên.
- Calibration webcam (phải HTTPS).
- Gaze WebSocket ghi sample.
- Upload PDF → content-worker → index → chatbot.
- Teacher → Trực quan hoá → Replay/Tổng hợp/heatmap.
- Chat streaming SSE.
- Restart stack, dữ liệu vẫn còn.

Kiểm tra real IP:

- Nginx access log / backend log phải thấy IP người dùng, không phải IP
  cloudflared (`172.x`).
- Nếu thấy cùng một IP cho mọi user, kiểm tra `CF-Connecting-IP` và
  `real_ip_header` trong nginx.

---

## 8. Backup và restore

Stack có volume `backups` đã được `backup-init` chown cho user postgres.

### Backup

Trong Portainer → Containers → postgres → Console:

```bash
pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc \
  -f "/backups/eyelearning-$(date +%Y%m%d-%H%M%S).dump"
```

Tải file:

- Portainer → Volumes → `eyelearning-prod_backups` → Browse → Download.

### Restore

1. Stop backend, content-worker, worker, embedding-worker, chatbot.
2. Upload file `.dump` vào volume `backups` qua Portainer volume browser.
3. Trong container postgres:

```bash
pg_restore --clean --if-exists --file=- /backups/<file>.dump \
  | sed "s/set_config('search_path', '', false)/set_config('search_path', 'public', false)/" \
  | psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1
```

4. Start lại backend/worker/chatbot.
5. Kiểm tra `app_metadata.schema_generation = 13`.

Không restore dump schema cũ vào code mới nếu generation khác; phải backup rồi
reset/restore đúng quy trình.

### Lưu ý volume

- Stack name phải giữ nguyên. Đổi tên stack → volume mới → mất dữ liệu.
- Không bấm xóa volume khi Remove stack.
- Không dùng `docker compose down -v` (không có host CLI, nhưng đừng làm qua
  Portainer).

---

## 9. Update và rollback

### Update

1. Push code/tag mới.
2. GitHub Actions build + push image.
3. Portainer webhook tự redeploy, hoặc bấm **Re-pull image and redeploy**.
4. Nếu dùng tag cố định, đổi `IMAGE_TAG` trong stack env rồi update stack.

### Rollback code

- Đổi `IMAGE_TAG` về tag cũ (`v1.0.4`, `sha-...`) → update stack.
- Nếu migration mới đã chạy: không có down migration; restore DB backup.

### Rollback Cloudflare

- Đổi public hostname về tunnel cũ / `http://localhost:3000`.
- Bật lại cloudflared local:
  ```bash
  systemctl --user start cloudflared
  ```

---

## 10. Bảo mật production

- `COOKIE_SECURE=true`, `DEBUG=false`, `OTP_DEV_ECHO=false`.
- Không chạy seed dev.
- Đổi toàn bộ mật khẩu seed/test.
- `JWT_SECRET`, `OTP_HASH_SECRET`, `CHATBOT_INTERNAL_TOKEN`, DB password:
  `openssl rand -hex 32`.
- Không commit `stack.env`, `.env`, file backup, tunnel token.
- Chỉ cloudflared nhận traffic; không publish port host.
- R2 key: cấp quyền tối thiểu cho bucket.
- SMTP: dùng app password/relay riêng cho production.
- Cloudflare: bật HTTPS, không bật Rocket Loader/Auto Minify nếu làm hỏng
  Next.js; có thể bật WAF/rate limit bổ sung.

---

## 11. Lỗi thường gặp

| Hiện tượng | Kiểm tra |
|---|---|
| `cloudflared` 502 | Ingress phải là `http://nginx:80`; cloudflared và nginx cùng stack network; nginx healthy |
| Tất cả user cùng một IP / OTP bị chặn | `real_ip_header CF-Connecting-IP` + `set_real_ip_from` trong nginx; xem lại image nginx mới |
| `migrate` exit 1 | Log migrate; checksum migration; DB cũ; sai `POSTGRES_PASSWORD` |
| Backend không healthy | Log backend; DSN; schema generation; Redis |
| Chatbot chưa ready | Weights HuggingFace; `chatbot_reader` role; `LLM_*`/`VLM_*` |
| Gaze chưa ready | GPU driver/toolkit; weights Google Drive/HF; egress |
| GHCR `401/403` | Package private; thêm registry credential trong Portainer |
| `pull access denied` | Sai `IMAGE_PREFIX`/`IMAGE_TAG`; image chưa build xong |
| Login không giữ phiên | `COOKIE_SECURE=true` + truy cập HTTPS; `CORS_ORIGINS` nếu frontend gọi API khác origin |
| Upload slide lỗi | content-worker log; LibreOffice; dung lượng disk |
| `permission denied /backups` | `backup-init` chưa chạy exit 0; xem volume `backups` |
| Portainer không build được | Stack này cố ý không có `build:`; chỉ pull image |
