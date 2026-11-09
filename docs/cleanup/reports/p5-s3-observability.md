# P5-S3 — Observability, backup, operations docs

## Summary

Thêm logging có thể cấu hình (`LOG_FORMAT=text|json`, `LOG_LEVEL`), script
backup/restore PostgreSQL, tài liệu vận hành và cập nhật README. Không đổi API,
route, auth hay schema generation.

Theo coordination update, `backend/app/main.py` **không bị sửa** trong branch
này để tránh conflict với S1. Coordinator cần thêm snippet ở mục dưới.

## Files changed

| File | Change |
|---|---|
| `backend/app/core/logging.py` | Mới — `configure_logging()`, `JsonFormatter` |
| `scripts/backup.sh` | Mới — backup/restore PostgreSQL có xác nhận |
| `docs/cleanup/OPERATIONS.md` | Mới — backup/restore, maintenance, logging, cảnh báo `down -v` |
| `README.md` | Thêm mục "Backup & bảo trì" |
| `.gitignore` | Thêm `backups/` |
| `docs/cleanup/reports/p5-s3-observability.md` | Report này |

Không thay đổi: `backend/app/main.py`, `backend/app/models/**`,
`backend/app/api/**`, `backend/app/services/**`, `db/migrations/**`,
`frontend/**`, `docker-compose.yml`, `.env`.

## Coordinator action — wire logging vào `main.py`

Thêm import sau `from app.core.config import settings`:

```python
from app.core.logging import configure_logging
```

Gọi trước khi tạo FastAPI app (ngay trước dòng `app = FastAPI(...)`):

```python
configure_logging()
app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
```

`configure_logging()` idempotent nên gọi lại (ví dụ trong test) không nhân đôi
handler.

## Behavior

### Logging (`backend/app/core/logging.py`)

- `LOG_FORMAT` mặc định `text`, giữ nguyên format hiện tại:
  `%(asctime)s %(levelname)s %(name)s: %(message)s`.
- `LOG_FORMAT=json`: mỗi bản ghi một dòng JSON với `timestamp` (UTC ISO 8601),
  `level`, `logger`, `message`; thêm `request_id` nếu record có
  `extra={"request_id": ...}`; thêm `exception` nếu có `exc_info`.
- `LOG_LEVEL` mặc định `INFO`; giá trị không hợp lệ fallback về `INFO`.
- Idempotent: handler riêng được đánh dấu `_eyelearning_handler`; gọi nhiều lần
  chỉ cập nhật level/format, không thêm handler trùng.

### Backup/restore (`scripts/backup.sh`)

- `./scripts/backup.sh` → `backups/eyelearning-YYYYmmdd-HHMMSS.dump`
  (`pg_dump --format=custom` trong container `postgres`).
- Ghi ra file `.partial` rồi `mv` để không để lại dump dở khi lỗi.
- `--restore <file>` dùng `pg_restore --clean --if-exists`, hỏi xác nhận
  `[y/N]`; `--yes` bỏ qua xác nhận.
- Không tự chạy restore/không tự xoá dữ liệu.
- Workaround: `pg_restore` đặt `search_path` rỗng; baseline hiện tại dùng
  `unaccent()` không qualify trong generated column. Script chuyển
  `search_path` sang `public` trong SQL do `pg_restore` sinh ra rồi chạy qua
  `psql -v ON_ERROR_STOP=1`.

## Tests run

| Command | Result |
|---|---|
| `backend/.venv/bin/ruff check backend/app` | `All checks passed!` |
| `bash -n scripts/backup.sh` | pass |
| `COMPOSE_PROJECT_NAME=eyelearning TEST_DB=eyetracking_test_s3 ./scripts/test_backend.sh` (lần đầu) | `63 passed in 21.41s` |
| `COMPOSE_PROJECT_NAME=eyelearning TEST_DB=eyetracking_test_s3 ./scripts/test_backend.sh` (lần sau) | 39 passed, 24 errors — DB generation 7 vs backend 6 (xem Risks) |
| pytest tương đương với baseline image của branch này | `63 passed in 20.74s` |

`COMPOSE_PROJECT_NAME=eyelearning` cần thiết vì worktree có tên thư mục khác
project compose đang chạy; stack hiện tại thuộc project `eyelearning` ở repo
chính.

Chi tiết lần chạy pytest cuối (do `eyelearning-migrations:local` đã bị S1
rebuild sang schema generation 7):

```bash
docker build -q -t eyelearning-migrations:s3-baseline ./db
docker exec eyetracking-postgres psql -U postgres -d postgres \
  -c 'DROP DATABASE IF EXISTS eyetracking_test_s3;' \
  -c 'CREATE DATABASE eyetracking_test_s3;'
docker run --rm --network eyelearning_default \
  -e PGHOST=postgres -e PGUSER=postgres -e PGPASSWORD=... \
  -e PGDATABASE=eyetracking_test_s3 \
  eyelearning-migrations:s3-baseline
cd backend
TEST_DATABASE_URL="postgresql+asyncpg://postgres:...@127.0.0.1:5435/eyetracking_test_s3" \
  .venv/bin/pytest -q
# 63 passed in 20.74s
```

Kiểm tra backup/restore thủ công:

- `./scripts/backup.sh` tạo `backups/eyelearning-20261109-145946.dump` (492K).
- `pg_restore --list` đọc dump OK (430 TOC entries, custom format).
- Restore pipeline vào database tạm `eyetracking_restore_s3` OK: 51 bảng,
  `schema_migrations` có 1 bản ghi.
- `--restore` + trả lời `n` → `Đã huỷ.` exit 1.
- `--restore` file không tồn tại → exit 1; `--yes` không kèm `--restore` → exit 2;
  `--help` OK.
- Database tạm và dump test đã được xoá sau khi kiểm tra.

## Risks

- **Compose chưa truyền `LOG_FORMAT`/`LOG_LEVEL`**: `docker-compose.yml` chỉ
  truyền các biến khai báo trong `x-backend-env`. Muốn dùng trong full Docker
  phải thêm 2 biến này (compose owner/S1) hoặc chạy tạm với
  `docker compose run -e ...`. Đã ghi chú trong `OPERATIONS.md`.
- **Restore workaround `unaccent`**: baseline dùng `unaccent()` không qualify;
  script đổi `search_path` khi restore. Giải pháp bền vững là qualify
  `public.unaccent` trong migration mới (S1), khi đó workaround vẫn vô hại.
- **Shared migrations image race**: S1 đã rebuild `eyelearning-migrations:local`
  với `002_embedding_jobs.sql` (schema generation 7), trong khi branch này
  (base `cleanup/integration`) vẫn là generation 6. `test_backend.sh` dùng image
  chung nên lần chạy sau fail `DB='7', backend='6'`. Đã xác nhận lại 63 test
  bằng image baseline tạm của branch này. Final integration phải rebuild image
  từ migrations đã merge.
- **`scripts/maintenance.sh` thuộc S2**, chưa có trong branch này tại thời điểm
  viết; docs tham chiếu commit `e3c860b` của S2 (dọn auth/learning session hết
  hạn, có `--local`). Cần kiểm tra lại sau khi merge S2.
- **Chưa có unit test cho `configure_logging()`**: task card không yêu cầu file
  test mới và acceptance là 63 test hiện có. Nên thêm test khi wire vào
  `main.py` (text/json, idempotent, request_id).
- `configure_logging()` thêm handler vào root logger. Nếu một framework khác
  cấu hình root handler, có thể có log trùng; uvicorn hiện không cấu hình root
  nên không gặp trong stack này.

## Follow-ups

1. Coordinator thêm import + `configure_logging()` vào `backend/app/main.py`
   theo snippet trên.
2. Thêm `LOG_FORMAT`/`LOG_LEVEL` vào `x-backend-env` trong `docker-compose.yml`
   (S1/compose owner) để cấu hình được trong full Docker.
3. S1 qualify `public.unaccent` trong migration mới (hoặc sửa baseline trước khi
   phát hành) để restore không cần workaround `search_path`.
4. Thêm test cho `configure_logging()` khi wire vào main.
5. Sau khi merge S2, đối chiếu lại mục maintenance trong `OPERATIONS.md` với
   `scripts/maintenance.sh` thực tế.
