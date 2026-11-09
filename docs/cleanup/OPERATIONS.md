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

## Bảo trì định kỳ

`scripts/maintenance.sh` dọn dữ liệu hết hạn (auth session, learning session
quá hạn), tạo partition gaze_samples trước 3 tháng và drop partition cũ hơn
`GAZE_RETENTION_DAYS` (mặc định 180 ngày). Script idempotent, không xoá volume
và không reset database.

```bash
./scripts/maintenance.sh          # chạy trong Docker (service backend phải đang chạy)
./scripts/maintenance.sh --local  # chạy bằng backend/.venv trên host
```

Khuyến nghị chạy định kỳ bằng cron/systemd timer (ví dụ mỗi ngày hoặc mỗi
tuần). Khi chạy `--local`, script tự trỏ `DATABASE_URL` về Postgres đã publish
ở `127.0.0.1:5435` nếu caller chưa set.

Tạo partition `gaze_samples` vẫn dùng script riêng:

```bash
./scripts/create_partitions.sh 3
```

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
