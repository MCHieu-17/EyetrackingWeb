# P2-B4 — Lesson access helpers + shared worker loop

- Branch: `cleanup/p2-b4-access-worker`
- Base: `cleanup/integration`
- Date: 2026-11-09

## Summary

Removed repeated lesson-access boilerplate and shared the worker loop without
changing API paths, response shapes, status codes, messages, or auth behavior.

1. **Lesson access helpers** — added to `backend/app/api/access.py`:
   - `get_lesson_with_course(db, lesson_id)` — loads lesson + course, 404 if
     either is missing (the old `_course_for_lesson` logic from `lessons.py`).
   - `get_managed_lesson(db, lesson_id, user)` — same load, then
     `can_manage_course`; raises 403 `"Không có quyền"` on failure.
   - `get_viewable_lesson(db, lesson_id, user)` — loads the lesson with
     `get_lesson_or_404`, then the course with `course_of_lesson` (returns
     `None` when missing), then `can_access_course`; raises 403
     `"Không có quyền"` if the course is missing or access is denied. This
     preserves the old `get_lesson_viewable` behavior exactly.
   - `get_lesson_viewable` delegates to `get_viewable_lesson` and still
     returns only the `Lesson`, so `analytics.py` is unchanged.
   - `course_of_lesson` is retained for the viewable path; routes that used
     `_course_for_lesson` keep the 404 behavior via `get_lesson_with_course`.
2. **`lessons.py`** — replaced every `_course_for_lesson` +
   `can_manage_course`/`can_access_course` + 403 block with the new helpers.
   `get_lesson_contents` keeps its special enrollment fallback by using
   `get_lesson_with_course` and then checking enrollment as before.
3. **`worker_loop.py`** — new reusable `run_worker_loop(name, poll_seconds,
   step, *, limit=None, max_iterations=None, unit="item(s)")`:
   - logs `<name> worker started`;
   - calls `step(limit=limit)` when `limit` is set, otherwise `step()`;
   - logs `processed <n> <unit>` when the result is truthy;
   - catches `Exception` with `logger.exception("<name> worker iteration
     failed")`;
   - sleeps `poll_seconds` between iterations;
   - `max_iterations` is test-only (default `None` = infinite).
4. **Workers** — `content_worker.py` and `worker.py` now call
   `run_worker_loop` with the same poll intervals (`content_worker_poll_seconds`
   and `worker_poll_seconds`), limits (`1` and `10`), and log message text.
5. **Tests** — added `backend/tests/test_worker_loop.py` covering:
   - one iteration with `limit` and the processed log;
   - one iteration without `limit`;
   - exception is logged and the loop continues;
   - cancellation/timeout propagates (`asyncio.wait_for`).
   Added `backend/tests/test_access.py` covering:
   - `get_viewable_lesson` / `get_lesson_viewable` return 403
     `"Không có quyền"` when the lesson exists but its course is missing;
   - `get_lesson_with_course` still returns 404 `"Không tìm thấy khóa học"`
     in the same situation, preserving route behavior.

## Files changed

| File | Change |
|---|---|
| `backend/app/api/access.py` | +`get_lesson_with_course`, `get_managed_lesson`, `get_viewable_lesson`; `get_lesson_viewable` delegates; retain `course_of_lesson` for the 403-on-missing-course path |
| `backend/app/api/routes/lessons.py` | use the new access helpers; remove `_course_for_lesson` and unused model imports |
| `backend/app/worker_loop.py` | new shared async worker loop |
| `backend/app/content_worker.py` | use `run_worker_loop` |
| `backend/app/worker.py` | use `run_worker_loop` |
| `backend/tests/test_worker_loop.py` | new worker-loop tests |
| `backend/tests/test_access.py` | new access-helper tests |
| `docs/cleanup/reports/p2-b4-access-worker.md` | this report |

No forbidden files (`services/**`, `models/**`, other `api/routes/**`,
`db/migrations/**`, `frontend/**`, `docker-compose.yml`, `README.md`, `.env`)
were modified.

## Tests run

```text
$ backend/.venv/bin/ruff check backend/app backend/tests
All checks passed!

$ TEST_DB=eyetracking_test_b4 ./scripts/test_backend.sh
...
[test_backend] chạy pytest
.........................................                                [100%]
41 passed in 12.78s
[test_backend] OK
```

41 = 34 existing tests + 4 worker-loop tests + 3 access-helper tests.

### Environment note

The worktree has no `.env` (gitignored, not copied by
`scripts/worktree_setup.sh`). A local untracked symlink
`.env -> ../../EyeLearning/.env` was created to run the unmodified test script,
and the script was run with `COMPOSE_PROJECT_NAME=eyelearning` so it targets the
already-running stack. No scripts or tracked config were modified.

## Risks

- **Logger name**: worker log records now come from `app.worker_loop` instead
  of `app.content_worker` / `app.worker`. Message text, levels, and poll
  intervals are unchanged. If log routing/alerting filters on logger name,
  update it to `app.worker_loop`.
- **Two missing-course behaviors are intentional**: `get_lesson_with_course`
  (used by routes that previously called `_course_for_lesson`) raises 404
  `"Không tìm thấy khóa học"`, while `get_viewable_lesson` /
  `get_lesson_viewable` raise 403 `"Không có quyền"` when the course is
  missing. This matches the previous behavior of each call site.
- **Worker loop `unit` parameter**: added only to preserve the existing
  processed-log wording; default is `"item(s)"`.

## Follow-ups

- P2 Phase 3 can reuse `get_lesson_with_course` / `get_viewable_lesson` when
  reducing ORM loads in media/quiz/AOI routes.
- If log routing depends on logger names, add an optional logger parameter to
  `run_worker_loop` or configure the logger name at the call site.
