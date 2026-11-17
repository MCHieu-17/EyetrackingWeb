# Vận hành — backup, bảo trì, logging

Tài liệu cho stack local. Mọi lệnh chạy từ thư mục gốc repo.

## Backup / restore PostgreSQL

`scripts/backup.sh` đọc `POSTGRES_USER`/`POSTGRES_DB` từ `.env`, chạy `pg_dump`
trong container `postgres` và ghi file custom-format vào `backups/`
(thư mục này đã được gitignore).

```bash
# Tạo backup
./scripts/backup.sh
# → backups/eyelearning-YYYYmmdd-HHMMSS.dump

# Khôi phục (hỏi xác nhận)
./scripts/backup.sh --restore backups/eyelearning-20261109-120000.dump

# Khôi phục không hỏi xác nhận (dùng cho script/khẩn cấp)
./scripts/backup.sh --restore backups/eyelearning-20261109-120000.dump --yes
```

Lưu ý:

- Restore dùng `pg_restore --clean --if-exists`, tức là **xoá/ghi đè object**
  trong database hiện tại. Nên dừng backend và các worker trước để tránh kết
  nối đang giữ object:
  `docker compose stop backend worker content-worker`
- Script chạy SQL do `pg_restore` sinh ra qua `psql` với `search_path=public`
  để tương thích baseline hiện tại (`unaccent()` không qualify trong generated
  column). Nếu baseline sau này qualify `public.unaccent`, bước này vẫn an toàn.
- File backup nằm trên host tại `backups/`, không nằm trong Docker volume.
  Copy ra ổ khác hoặc backup ngoài máy nếu cần giữ lâu dài.
- Script tự giữ tối đa `BACKUP_KEEP` file gần nhất (mặc định 7):
  `BACKUP_KEEP=14 ./scripts/backup.sh`.
- Đường dẫn trong `--restore` được tính từ thư mục gốc repo (script `cd` về đó).
- Không commit file backup: `backups/` đã có trong `.gitignore`.

## Xoá lịch sử gaze/visualization

Khi cần nghiệm thu lại từ đầu, dùng script có guard thay vì reset cả database:

```bash
# Xem trước số row sẽ bị xoá (không xoá gì)
./scripts/reset_gaze_data.sh --all
./scripts/reset_gaze_data.sh --course-id <course-uuid>

# Backup tự động rồi xoá
./scripts/reset_gaze_data.sh --all --apply --confirm-reset-gaze
```

Script chỉ xoá `course_visits` (cascade `learning_sessions` →
`content_views` → `view_layouts`/`gaze_samples`) và huỷ job
`analyze_lesson` đang chờ. Nội dung khóa học, slide, AOI, người dùng và
calibration được giữ nguyên. `--skip-backup` chỉ dùng khi đã tự backup.

## SMTP gửi OTP

- Cấu hình `SMTP_HOST/PORT/USER/PASS` trong `.env`; `SMTP_FROM` mặc định là
  `SMTP_USER`, `SMTP_REPLY_TO` mặc định là địa chỉ From. Port 587 dùng
  STARTTLS, port 465 đặt `SMTP_USE_SSL=true`. Nếu mật khẩu/app password có
  khoảng trắng, đặt trong dấu nháy kép (`SMTP_PASS="..."`) để `source .env`
  và Docker Compose đọc đúng.
- `OTP_TTL_SECONDS` mặc định 900 (15 phút) để kịp thời gian Microsoft 365
  chuyển thư từ người gửi mới vào Inbox/Junk.
- Backend chỉ ghi log lỗi gửi mail an toàn; không ghi mã OTP ở production.
- Đổi cấu hình SMTP cần recreate backend: `docker compose up -d backend`.
- Email OTP cố ý không chèn link để giảm nguy cơ bị Microsoft 365 gắn cờ
  phishing. Nếu sinh viên không thấy mã, hướng dẫn kiểm tra **Thư rác** và
  **Quarantine** của hộp thư Outlook trường trước khi gửi lại.
- Gmail thường bị chậm/hộp thư rác khi gửi lần đầu tới `st.neu.edu.vn`. Với
  lớp học đông, nên dùng SMTP relay/transactional provider có domain gửi đã
  cấu hình SPF/DKIM/DMARC thay vì Gmail cá nhân.
- Nếu log có `550 5.4.1 Recipient address rejected: Access denied`, địa chỉ
  sinh viên không tồn tại trong tenant Microsoft 365 (DBEB) — không phải lỗi
  cấu hình SMTP. Không gửi lại liên tục vì bounce làm giảm uy tín người gửi.
- Mailer kiểm tra cả danh sách người nhận bị SMTP từ chối; trường hợp này API
  trả `email_send_failed` thay vì báo thành công giả.

## Migration generation 13

`002_email_otp.sql` và `003_aoi_single_label.sql` là migration **destructive**:
bỏ `oauth_accounts`, `gaze_samples.aoi_codes`, `slides.aoi_suggestions`.
`005_current_viewport_only.sql` cũng destructive: chuyển `view_layouts` cũ
sang viewport hiện tại rồi bỏ `coordinate_space`, `visible_rect` và
`gaze_samples.original_viewport_x/y`. Không có down migration.
`004_content_view_aoi_stats.sql` là migration additive: thêm
`content_views.aoi_stats` cho dashboard Trực quan hoá. Trước khi chạy:

```bash
./scripts/backup.sh
# Dừng backend/worker cũ trước khi drop cột.
docker compose stop backend worker content-worker
docker compose run --rm migrate
docker compose up -d backend worker content-worker frontend
```

Nếu cần rollback code cũ, phải restore backup database. Sau migration, chạy
`docker compose exec backend python -m app.reanalyze` để tính lại nhãn AOI,
`heatmap_grid` và `aoi_stats`.

`GAZE_FPS` (mặc định 15, hợp lệ 1..60) là nguồn duy nhất cho tần số gaze:
backend trả lại qua `GET /api/config`, gaze throttle `1000/FPS × 0.95`, worker
suy ra ngưỡng gap `max(250, 3000/FPS)`. Đổi giá trị cần restart backend + gaze
và worker phân tích (`docker compose up -d backend worker gaze`); frontend đọc
runtime nên không rebuild.

## Bảo trì định kỳ

`scripts/maintenance.sh` dọn dữ liệu hết hạn (auth session, learning session
quá hạn, course visit idle quá 30 phút, `email_otps` hết hạn quá 1 ngày) và xoá
gaze sample cũ hơn `GAZE_RETENTION_DAYS` (mặc định 180 ngày).
Schema generation 13 không dùng partition. Script idempotent, không xoá volume
và không reset database.

```bash
./scripts/maintenance.sh          # chạy trong Docker (service backend phải đang chạy)
./scripts/maintenance.sh --local  # chạy bằng backend/.venv trên host
```

Khuyến nghị chạy định kỳ bằng cron/systemd timer (ví dụ mỗi ngày hoặc mỗi
tuần). Khi chạy `--local`, script tự trỏ `DATABASE_URL` về Postgres đã publish
ở `127.0.0.1:5435` nếu caller chưa set.

## Logging

Backend cấu hình logging qua `backend/app/core/logging.py`
(`configure_logging()` được gọi khi khởi động trong `backend/app/main.py`).

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Mức log: `DEBUG`, `INFO`, `WARNING`, `ERROR`... |
| `LOG_FORMAT` | `text` | `text` giữ format hiện tại; `json` xuất mỗi dòng một JSON object |

Ví dụ trong `.env`:

```env
LOG_LEVEL=INFO
LOG_FORMAT=json
```

Format text (mặc định):

```text
2026-11-09 12:00:00,000 INFO app.performance: request id=... method=GET ...
```

Format JSON — mỗi bản ghi một dòng, gồm `timestamp`, `level`, `logger`,
`message`, và `request_id` nếu log record được gắn
`extra={"request_id": ...}`:

```json
{"timestamp": "2026-11-09T05:00:00.000000+00:00", "level": "INFO", "logger": "app.performance", "message": "request id=... method=GET ..."}
```

Lưu ý khi chạy full Docker: compose chỉ truyền các biến được khai báo trong
`docker-compose.yml`. Nếu `LOG_FORMAT`/`LOG_LEVEL` chưa có trong
`x-backend-env`, thêm chúng vào đó (thuộc phạm vi compose) hoặc chạy tạm:

```bash
docker compose run --rm -e LOG_FORMAT=json -e LOG_LEVEL=DEBUG backend
```

Khi chạy backend trên host, export biến trước khi khởi động uvicorn:

```bash
cd backend
LOG_FORMAT=json LOG_LEVEL=DEBUG .venv/bin/python -m uvicorn app.main:app --reload --port 8001
```

Đổi biến môi trường cần restart tiến trình backend để có hiệu lực.

## Cảnh báo mất dữ liệu

`docker compose down -v` **xoá toàn bộ volume**, gồm database PostgreSQL,
media upload, weights gaze/chatbot và Redis. Chỉ dùng khi thật sự muốn reset
sạch. Trước khi chạy, tạo backup bằng `./scripts/backup.sh` và chắc chắn không
cần dữ liệu cũ.

```bash
# Dừng container, GIỮ volume/dữ liệu
docker compose down

# Dừng container + XOÁ volume — mất DB, media, weights
docker compose down -v
```
