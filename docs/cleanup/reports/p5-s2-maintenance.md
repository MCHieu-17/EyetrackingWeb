# P5-S2 — Maintenance worker cho session hết hạn

- Branch: `cleanup/p5-s2-maintenance`
- Base: `cleanup/integration` (`9f4b70f`)
- Date: 2026-11-09
- Scope: thêm module maintenance + script + test; **không đổi API, schema hay
  hành vi request**.

## Summary

Thêm cơ chế dọn dẹp dữ liệu hết hạn, chạy thủ công hoặc qua cron:

1. `backend/app/maintenance.py`
   - `delete_expired_auth_sessions(db, *, now=None) -> int`: xoá
     `auth_sessions` có `expires_at < now`, bao gồm cả session đã thu hồi
     (`revoked_at IS NOT NULL`) và đã hết hạn. Trả về số dòng đã xoá.
   - `expire_stale_learning_sessions(db, *, now=None) -> int`: cập nhật
     `learning_sessions.status = 'expired'`, `ended_at = now` cho các session
     `in_progress` đã quá `expires_at`. Không xoá dòng, không đụng gaze sample,
     analysis run hay dữ liệu khoá học. Trả về số dòng đã cập nhật.
   - `run_maintenance() -> dict[str, int]`: mở `SessionLocal`, chạy cả hai bước
     trong một transaction, commit, trả về
     `{"auth_sessions_deleted": ..., "learning_sessions_expired": ...}`.
   - `main()` + `if __name__ == "__main__"` để chạy `python -m app.maintenance`.
   - Mọi mốc thời gian dùng `datetime.now(timezone.utc)`; tham số `now` naive
     được chuẩn hoá thành UTC, `now` có timezone được đổi về UTC.
2. `scripts/maintenance.sh`
   - Mặc định: `docker compose exec -T backend python -m app.maintenance`.
   - `--local`: chạy `backend/.venv/bin/python -m app.maintenance` từ repo root
     với `PYTHONPATH` trỏ tới `backend/`. Script source `.env`, tự suy ra
     `DATABASE_URL` từ `DATABASE_URL_DOCKER` (đổi host `postgres:5432` thành
     `127.0.0.1:5435`) nếu caller chưa set, và đặt mặc định
     `AI_HTTP_URL=http://localhost:8000` để `Settings` khởi tạo được ngoài
     Docker.
   - `--help`, tham số lạ trả exit 2; `set -euo pipefail`.
3. `backend/tests/test_maintenance.py` — 2 integration tests:
   - Seed auth session hết hạn, session đã thu hồi + hết hạn, và một session
     còn hiệu lực; assert xoá đúng 2 dòng và chỉ còn session còn hiệu lực.
   - Seed hai learning session `in_progress` (một quá hạn, một còn hạn); assert
     chỉ session quá hạn chuyển `expired` với `ended_at` được set, session còn
     hạn giữ nguyên `in_progress`/`ended_at = NULL`.
   - Dọn các dòng do test tạo trong `finally`.

Không thay đổi `backend/app/models/**`, `backend/app/api/**`,
`backend/app/services/**`, `backend/app/main.py`, migrations, frontend,
`docker-compose.yml`, `README.md` hay `.env`.

## Files changed

| File | Change |
|---|---|
| `backend/app/maintenance.py` | New: maintenance functions + CLI entry point |
| `scripts/maintenance.sh` | New: Docker/local runner |
| `backend/tests/test_maintenance.py` | New: 2 integration tests |
| `docs/cleanup/reports/p5-s2-maintenance.md` | This report |

## Tests run

```text
$ backend/.venv/bin/ruff check backend/app backend/tests
All checks passed!

$ bash -n scripts/maintenance.sh
(no output — OK)

$ COMPOSE_PROJECT_NAME=eyelearning TEST_DB=eyetracking_test_s2 ./scripts/test_backend.sh
...
65 passed in 22.51s
[test_backend] OK

$ bash -n scripts/maintenance.sh
(no output — OK)

$ DATABASE_URL=... ./scripts/maintenance.sh --local   # DB tạm đã migrate
[maintenance] chạy local bằng backend/.venv
[maintenance] deleted 0 expired auth session(s)
[maintenance] expired 0 stale learning session(s)
```

65 = 63 existing tests + 2 new maintenance tests.

Ghi chú môi trường: worktree không có `.env` (gitignored). Đã copy `.env` từ
repo chính và chạy test với `COMPOSE_PROJECT_NAME=eyelearning` để dùng stack
Postgres đang chạy sẵn; không sửa file nào của repo chính.

## Risks

- **Xoá auth session là không thể hoàn tác.** Hàm chỉ xoá session đã hết hạn
  (kể cả đã thu hồi), nhưng nếu chạy với `now` sai (ví dụ truyền nhầm thời
  điểm tương lai) có thể xoá session còn hiệu lực. `run_maintenance()` luôn
  dùng UTC hiện tại; các caller khác phải cẩn thận khi truyền `now`.
- **Không có index trên `expires_at`.** `auth_sessions` chỉ có index
  `user_id` và unique `refresh_token_hash`; `learning_sessions` có index
  `status` nhưng không có `expires_at`. Với dữ liệu lớn, câu DELETE/UPDATE có
  thể scan bảng. Không thêm migration trong task này (migrations thuộc S1
  Phase 5).
- **Chạy đồng thời.** Hai tiến trình maintenance chạy cùng lúc vẫn an toàn về
  mặt dữ liệu (DELETE/UPDATE idempotent), nhưng có thể cùng quét bảng và trả
  về count khác nhau tuỳ thời điểm. Nên chạy một instance duy nhất.
- **Transaction chung.** `run_maintenance()` commit cả hai bước trong một
  transaction; nếu bước hai lỗi, bước xoá auth session cũng rollback. Đây là
  chủ ý để tránh trạng thái nửa vời, nhưng nghĩa là một lỗi ở learning session
  sẽ chặn dọn auth session cho tới lần chạy sau.
- **Không có logging/metrics.** Script chỉ in count ra stdout; chưa có
  structured log hay metric để theo dõi trên production.
- **Chưa có lịch chạy.** Task chỉ cung cấp script; chưa gắn cron/systemd timer
  hay worker loop.
- **`--local` giả định Postgres publish ở `127.0.0.1:5435`.** Nếu đổi port
  trong compose, caller phải export `DATABASE_URL` đúng; script chỉ tự suy ra
  từ `DATABASE_URL_DOCKER` khi biến này chưa có.

## Follow-ups

1. Thêm lịch chạy (cron/systemd timer hoặc worker loop) và log có cấu trúc
   (số dòng xoá/cập nhật, thời gian chạy, lỗi).
2. Cân nhắc migration thêm index cho `auth_sessions(expires_at)` và
   `learning_sessions(status, expires_at)` khi dữ liệu tăng (S1/Phase 5 sở hữu
   migrations).
3. Thêm chế độ `--dry-run` để đếm trước khi xoá/cập nhật.
4. Định nghĩa retention policy riêng cho gaze sample/analysis run nếu cần;
   task này cố ý không xoá các dữ liệu đó.
5. Cân nhắc gộp maintenance vào worker hiện có thay vì cron riêng, để dùng
   chung connection pool và logging.
