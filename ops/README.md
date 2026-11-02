# ops/ — Script vận hành local

Bộ script hỗ trợ stack Docker local. Không chứa secret — credential đọc từ `.env`.

## `build_ai_base.sh` — build image nền dùng chung

Build `eyelearning-ai-base:latest` (torch/torchvision CUDA 12.4) mà
`services/gaze` và `services/chatbot` `FROM`. Phải có image này trước khi build
2 service đó.

```bash
./ops/build_ai_base.sh
```

## `create_chatbot_role.sh` — role DB hạn chế cho chatbot

Tạo/cập nhật role `chatbot_reader` (đọc course/lesson/slide + ghi embedding,
**không** đọc bảng quiz/users). Chạy một lần sau khi migrations đã áp:

```bash
./ops/create_chatbot_role.sh
```

Script đọc `POSTGRES_*`, `CHATBOT_DB_USER`, `CHATBOT_DB_PASSWORD` từ `.env` gốc
repo và chạy `psql` trong container `postgres`; idempotent nên chạy lại để đổi
password/grant cũng được.

## `maintain_partitions.sql` — bảo trì partition gaze_events

Gọi `create_gaze_partitions(3)` để tạo partition tháng mới:

```bash
docker compose exec -T postgres psql -U postgres -d eyetracking \
  -f - < ops/maintain_partitions.sql
```

## `docker_cleanup.sh` — dọn image/build cache

Chỉ `docker image prune` và `docker builder prune` cho tài nguyên cũ hơn 168h
(7 ngày).

> ⚠️ **KHÔNG BAO GIỜ prune volume.** Volume chứa `pgdata`, `backend-media`,
> `gaze-weights`, `chatbot-weights`, `redis-data`. Prune volume = mất dữ liệu.

```bash
./ops/docker_cleanup.sh
```

## Migration (schema DB)

Schema do các file trong `db/migrations/` quyết định. Runner `db/migrate.sh`
(nằm trong image `eyelearning-migrations:local`, service một-lần `migrate`) là
thứ duy nhất nên chạy migration — **không** `psql -f` tay từng file.

Cơ chế:

- Bảng `schema_migrations` lưu `filename` + `checksum` sha256 của mọi file đã áp;
  lần chạy sau **chỉ chạy file chưa áp**.
- File đã áp mà bị **sửa nội dung** → runner dừng ngay, in rõ checksum cũ/mới.
  Muốn đổi schema thì **thêm file mới** (`025_…`) — không sửa file cũ.
- DB cũ chưa có `schema_migrations` → chạy toàn bộ như trước rồi ghi dấu; mọi file
  đều idempotent nên an toàn.
- Service `migrate` exit 1 ⇒ compose huỷ lần chạy đó. Xem log:
  `docker logs eyetracking-migrate`.

Xem file nào đã áp:

```bash
docker compose exec -T postgres psql -U postgres -d eyetracking \
  -c "SELECT filename, applied_at, duration_ms FROM schema_migrations ORDER BY filename;"
```

Chạy migration tay:

```bash
docker compose run --rm migrate
```

Reset DB local (giữ weights):

```bash
./scripts/reset_db.sh
```

Ghi dấu mà KHÔNG chạy (chỉ khi DB đã đúng schema nhưng bảng tracking còn trống —
**không dùng khi DB đang thiếu migration**):

```bash
docker compose run --rm -e MIGRATE_BASELINE=1 migrate
```

## Kiểm tra dung lượng đĩa

```bash
df -h
docker system df
docker system df -v
```
