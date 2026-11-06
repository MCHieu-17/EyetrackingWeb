# Phase 0 — Test isolation

Mục tiêu: test không bao giờ chạm database development, media thật hoặc R2 thật.

## 1. Database

| Môi trường | Database | Ghi chú |
|---|---|---|
| Development | `eyetracking` | Chỉ reset qua `scripts/reset_db.sh --apply` có guard |
| Backend test | `eyelearning_refactor_test` | Tạo bằng `scripts/test_db.sh`; baseline Phase 1 |
| Chatbot test | `eyelearning_refactor_test` | Cùng DB, role `chatbot_reader` |
| Frontend E2E | `eyelearning_refactor_test` | Backend test chạy cổng `8011` |
| CI | `eyelearning_refactor_test` | Không dùng `eyetracking_test` cũ |

Quy tắc:

- Không tự động chạy migration trong `pytest` fixture. Test DB phải được dựng
  trước bằng runner chung (`scripts/test_db.sh`).
- Không dùng `Base.metadata.create_all()` thay baseline.
- Không drop database nếu chưa xác nhận ownership.
- Không log secret/DSN đầy đủ trong evidence.

## 2. Media/R2

- `MEDIA_DIR` trỏ `$TMPDIR/eyelearning-test-media` (backend test).
- `R2_*` để trống trong test; mọi test cleanup dùng local temp.
- Test nào cần R2 dùng mock/fake S3, không gọi bucket thật.
- Không chạy GC trên R2 thật trong Phase 2–5.

## 3. Redis

- Test dùng `REDIS_URL` trỏ DB Redis riêng (ví dụ `redis://localhost:6379/15`)
  hoặc để trống để fallback in-memory.
- Key namespace chứa `APP_INSTANCE_ID`; test dùng instance ID riêng.
- Không `FLUSHALL`.

## 4. Frontend E2E

`frontend/playwright.config.ts` đọc:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `E2E_BASE_URL` | `http://localhost:3012` | Next.js test server |
| `E2E_API_URL` | `http://localhost:8011` | Backend test, **không** phải `8001` |
| `E2E_GAZE_URL` | `http://localhost:8010` | Gaze test, **không** phải `8000` |

Nếu backend test chưa chạy, E2E phải fail rõ ràng thay vì âm thầm gọi backend
development.

## 5. DB instance namespace

- `APP_INSTANCE_ID` (UUID) đại diện một lần dựng DB.
- Media key: `instances/{APP_INSTANCE_ID}/courses/{course_id}/...`
- Redis key: `{APP_INSTANCE_ID}:...`
- `app_metadata` lưu `db_instance_id`, `schema_generation`.
- Client cũ (queue IndexedDB, cache) kiểm tra generation và bỏ batch cũ khi
  generation khác.

## 6. Lệnh

```bash
# Dựng test DB (Phase 1)
./scripts/test_db.sh

# Backend tests
./scripts/test_backend.sh

# Chatbot tests
./scripts/test_chatbot.sh

# Frontend unit
cd frontend && npm test

# Frontend E2E (cần backend test cổng 8011)
cd frontend && npm run test:e2e
```
