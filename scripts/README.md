# scripts/ — Dev + vận hành local

Script hỗ trợ stack Docker local. Không chứa secret — credential đọc từ `.env`
gốc repo.

## Dev

| Script | Mục đích |
|---|---|
| `check.sh` | Kiểm tra nhanh trạng thái stack |
| `seed_dev.sh` | Seed tài khoản dev (`admin@`, `teacher@`, `student@`) |
| `reset_db.sh` / `reset_db.py` | Reset DB development có guard |
| `test_backend.sh` | Chạy test backend |
| `test_migrations.sh` | Test migration runner + checksum/idempotent |
| `tests/test_reset_db.py` | Guard tests cho reset (stdlib unittest) |
| `smoke.sh` | Smoke test sau khi stack lên |

## `create_chatbot_role.sh` — role DB hạn chế cho chatbot

Tạo/cập nhật role `chatbot_reader` (đọc course/lesson/slide + ghi embedding,
**không** đọc bảng quiz/users). Bình thường **không cần chạy tay**: service
`migrate` tự gọi `db/chatbot_role.sql` sau mỗi lần áp migrations. Script này
dùng khi muốn cấp lại quyền/đổi password ngay:

```bash
./scripts/create_chatbot_role.sh
```

Script đọc `POSTGRES_*`, `CHATBOT_DB_USER`, `CHATBOT_DB_PASSWORD` từ `.env` gốc
repo và chạy `psql` trong container `postgres`; idempotent nên chạy lại để đổi
password/grant cũng được.

## Retention gaze

Schema generation 12 dùng bảng `gaze_samples` thường, không partition. Chạy
`./scripts/maintenance.sh` để xoá sample cũ hơn `GAZE_RETENTION_DAYS`.

## `docker_cleanup.sh` — dọn image/build cache

Chỉ `docker image prune` và `docker builder prune` cho tài nguyên cũ hơn 168h
(7 ngày).

> ⚠️ **KHÔNG BAO GIỜ prune volume.** Volume chứa `pgdata`, `backend-media`,
> `gaze-weights`, `chatbot-weights`, `redis-data`. Prune volume = mất dữ liệu.

```bash
./scripts/docker_cleanup.sh
```

`check.sh --full` chạy reset guard tests, backend/chatbot/gaze tests và frontend
unit tests. Có thể override interpreter bằng `BACKEND_PYTHON`,
`CHATBOT_PYTHON`, `GAZE_PYTHON` và `PYTEST_BIN`.

## Migration (schema DB)

Schema do các file trong `db/migrations/` quyết định. Hiện có baseline duy nhất
`001_baseline.sql` (generation 12, 24 bảng lõi); migration tiếp theo là
`002_...sql`. Runner `db/migrate.sh` (nằm trong image
`eyelearning-migrations:local`, build từ `db/Dockerfile`, service một-lần
`migrate`) là thứ duy nhất nên chạy migration — **không** `psql -f` tay từng file.

Cơ chế:

- Bảng `schema_migrations` lưu `filename` + `checksum` sha256 của mọi file đã áp;
  lần chạy sau **chỉ chạy file chưa áp**.
- File đã áp mà bị **sửa nội dung** → runner dừng ngay, in rõ checksum cũ/mới.
  Muốn đổi schema thì **thêm file mới** (`002_…`) — không sửa file cũ.
- DB cũ có bảng public nhưng chưa có `schema_migrations` → runner **fail** và yêu
  cầu reset có guard (`./scripts/reset_db.sh`). Không tự đoán schema cũ.
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
./scripts/reset_db.sh                 # preview
./scripts/reset_db.sh --apply --database eyetracking --confirm-reset eyetracking
```

## Kiểm tra dung lượng đĩa

```bash
df -h
docker system df
docker system df -v
```
