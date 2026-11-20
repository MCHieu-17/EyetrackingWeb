# scripts/ — Dev + vận hành local

Script hỗ trợ stack Docker local. Không chứa secret — credential đọc từ `.env`
gốc repo.

## Dev

| Script | Mục đích |
|---|---|
| `check.sh` | Kiểm tra chất lượng: ruff, lint, typecheck, compose config; `--full` thêm knip + build |
| `seed_dev.sh` | Seed tài khoản dev (`admin@`, `teacher@`, `student@`) |
| `reset_db.sh` / `reset_db.py` | Reset DB development có guard |
| `reset_gaze_data.sh` | Xoá lịch sử gaze/visualization có guard, giữ nội dung khóa học |
| `test_migrations.sh` | Kiểm tra migration runner + checksum/idempotent trên DB tạm |
| `test_fast.sh` | Backend + gaze + chatbot fast test (mock model/LLM) |
| `test_smoke.sh` | Gaze model + chatbot RAG + E2E smoke trước merge |
| `test_backend.sh` | Backend pytest trên DB `eyetracking_test` |
| `test_gaze.sh` | Gaze fast/smoke trong image test |
| `test_chatbot.sh` | Chatbot fast/smoke |
| `seed_e2e.py` | Seed course/quiz/gaze cho Playwright |
| `e2e.sh` | Seed + chạy Playwright trên stack local |
| `smoke.sh` | Smoke test sau khi stack lên |
| `backup.sh` | Backup/restore PostgreSQL local |
| `maintenance.sh` | Dọn session/OTP/gaze hết hạn |
| `docker_cleanup.sh` | Prune image + build cache cũ |
| `publish_images.sh` | Build/push image production lên GHCR (fallback nếu không dùng GitHub Actions) |
| `smoke_remote.sh` | Smoke test qua domain public, không cần SSH/Portainer |

Test tự động nằm trong image test riêng (`backend-test`, `chatbot-test`,
`gaze-test`) và mount thư mục `tests/` từ host; không cần cài pytest vào image
production. Chạy `make test-fast` sau mỗi lần sửa, `make test-smoke` trước merge.
Chi tiết phạm vi: `TEST_PLAN.md` ở root repo.

## Production qua Portainer

Hướng dẫn đầy đủ ở [`deploy/portainer/README.md`](../deploy/portainer/README.md).
Tóm tắt:

```bash
# Build/push thủ công nếu GitHub Actions không dùng được
docker login ghcr.io
IMAGE_PREFIX=ghcr.io/mchieu-17 IMAGE_TAG=v1.0.0 ./scripts/publish_images.sh

# Smoke test qua domain public
BASE_URL=https://eyetracking.nmhieu17.space ./scripts/smoke_remote.sh
```

Stack production dùng `deploy/portainer/docker-compose.yml`; chỉ pull image,
không build trên server, không publish port host. `cloudflared` nằm trong stack
và nhận traffic Cloudflare Tunnel.

## Role DB cho chatbot/admin

`db/migrate.sh` tự tạo/cập nhật role `chatbot_reader` và `admin_reader` sau mỗi
lần áp migrations khi `CHATBOT_DB_USER` + `CHATBOT_DB_PASSWORD` và
`ADMIN_DB_USER` + `ADMIN_DB_PASSWORD` có trong môi trường. Bình thường không cần
chạy tay. Khi muốn cấp lại quyền/đổi password ngay, chạy lại migration (idempotent):

```bash
docker compose run --rm migrate
```

Role `chatbot_reader` chỉ đọc view outline + đọc/ghi cột index trên `slides`,
không đọc bảng quiz/users. Role `admin_reader` chỉ đọc các bảng/cột an toàn cho
trang Truy vấn CSDL.

## Retention gaze

Schema generation 13 dùng bảng `gaze_samples` thường, không partition. Chạy
`./scripts/maintenance.sh` để xoá sample cũ hơn `GAZE_RETENTION_DAYS`.

Khi cần xoá sạch lịch sử gaze/visualization để test lại:

```bash
./scripts/reset_gaze_data.sh --all                  # preview
./scripts/reset_gaze_data.sh --all --apply --confirm-reset-gaze
./scripts/reset_gaze_data.sh --course-id <uuid>     # chỉ một khóa
```

Script tự backup trước khi xoá (trừ khi `--skip-backup`) và không xoá users,
courses, slides, AOIs hay calibration.

## `docker_cleanup.sh` — dọn image/build cache

Chỉ `docker image prune` và `docker builder prune` cho tài nguyên cũ hơn 168h
(7 ngày).

> ⚠️ **KHÔNG BAO GIỜ prune volume.** Volume chứa `pgdata`, `backend-media`,
> `gaze-weights`, `chatbot-weights`, `redis-data`. Prune volume = mất dữ liệu.

```bash
./scripts/docker_cleanup.sh
```

## Migration (schema DB)

Schema do các file trong `db/migrations/` quyết định. Hiện có
`001_baseline.sql` (generation 12, 24 bảng lõi), `002_email_otp.sql`,
`003_aoi_single_label.sql`, `004_content_view_aoi_stats.sql` và
`005_current_viewport_only.sql` (generation 13). Migration tiếp theo là
`006_...sql`.

Runner `db/migrate.sh` (nằm trong image `eyelearning-migrations:local`, build từ
`db/Dockerfile`, service một-lần `migrate`) là thứ duy nhất nên chạy migration —
**không** `psql -f` tay từng file.

Cơ chế:

- Bảng `schema_migrations` lưu `filename` + `checksum` sha256 của mọi file đã áp;
  lần chạy sau **chỉ chạy file chưa áp**.
- File đã áp mà bị **sửa nội dung** → runner dừng ngay, in rõ checksum cũ/mới.
  Muốn đổi schema thì **thêm file mới** (`006_…`) — không sửa file cũ.
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
