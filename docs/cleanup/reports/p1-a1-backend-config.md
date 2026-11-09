# P1-A1 — Backend config / dead-code cleanup

- Branch: `cleanup/p1-a1-backend-config`
- Base: `cleanup/integration`
- Date: 2026-11-09

## Summary

Low-risk backend cleanup, no API path/response changes:

1. **DB pool config** — added `db_pool_min` (default 5) and `db_pool_max`
   (default 20) to `Settings`. `db/session.py` now uses
   `pool_size=settings.db_pool_min` and
   `max_overflow=max(0, settings.db_pool_max - settings.db_pool_min)`.
   `pool_timeout=30`, `pool_recycle`, `pool_use_lifo` and connect args are
   unchanged. Defaults reproduce the previous effective pool (5 + 5).
   `docker-compose.yml` already forwards `DB_POOL_MIN`/`DB_POOL_MAX` to the
   backend, so no compose change was needed.
2. **Worker poll config** — added `worker_poll_seconds` (default 5.0).
   `worker.py` now reads `settings.worker_poll_seconds` instead of
   `os.getenv("WORKER_POLL_SECONDS", "5")`; the unused `os` import was removed.
3. **`escape_like` relocation** — moved from `app/api/access.py` to
   `app/core/helpers.py`. `access.py` re-exports it
   (`from app.core.helpers import escape_like as escape_like`), so existing
   `from app.api.access import escape_like` imports in
   `api/routes/courses.py` and `api/routes/admin.py` keep working.
4. **LIKE escaping in teacher course search** — `list_teacher_courses` now
   uses `CourseVersion.title.ilike(f"%{escape_like(q)}%", escape="\\")`,
   so `%`, `_` and `\` in the search term are treated literally.
5. **Dead code removal** — removed unused `mark_course_version_pending` from
   `app/services/embedding.py`. `mark_course_version_pending_in_session`
   (used by `api/routes/courses.py`) is untouched. Grep confirms no remaining
   references to the removed function.
6. **Tests** — added `backend/tests/test_helpers.py` (escape_like for
   backslash, `%`, `_`, plain text) and `backend/tests/test_config.py`
   (pool bounds consistency, positive worker poll interval).

## Files changed

| File | Change |
|---|---|
| `backend/app/core/config.py` | +`db_pool_min`, `db_pool_max`, `worker_poll_seconds` |
| `backend/app/db/session.py` | pool size/overflow from settings |
| `backend/app/worker.py` | poll interval from settings, drop `os` |
| `backend/app/core/helpers.py` | +`escape_like` |
| `backend/app/api/access.py` | re-export `escape_like`, remove local def |
| `backend/app/services/content.py` | escaped LIKE in `list_teacher_courses` only |
| `backend/app/services/embedding.py` | remove unused `mark_course_version_pending` |
| `backend/tests/test_helpers.py` | new |
| `backend/tests/test_config.py` | new |
| `docs/cleanup/reports/p1-a1-backend-config.md` | this report |

No forbidden files (`models/**`, `db/migrations/**`, `frontend/**`,
`docker-compose.yml`, `README.md`, `.env`) were modified.

## Tests run

```text
$ backend/.venv/bin/ruff check backend/app backend/tests
All checks passed!

$ TEST_DB=eyetracking_test_a1 ./scripts/test_backend.sh
...
[test_backend] chạy pytest
..................................                                       [100%]
34 passed in 12.73s
[test_backend] OK
```

34 = 28 existing tests + 6 new tests (4 helper, 2 config).

### Environment note

The worktree has no `.env` (gitignored, not copied by
`scripts/worktree_setup.sh`). To run the unmodified test script, a symlink
`.env -> ../../EyeLearning/.env` was created locally (untracked, not
committed). The script was run with `COMPOSE_PROJECT_NAME=eyelearning` so
`docker compose exec/run` targets the already-running stack instead of
creating a new compose project. No scripts were modified.

## Risks

- **Pool defaults**: `max_overflow` changes from 5 to 15 (20 − 5), so the
  default max connections per process rises from 10 to 20. This matches the
  existing compose defaults (`DB_POOL_MIN=5`, `DB_POOL_MAX=20`) and the
  intended `db_pool_max` semantics. Deployments that relied on the old
  hard-coded 10 should set `DB_POOL_MAX=10`.
- **LIKE escaping**: search terms containing `%`, `_` or `\` now match
  literally instead of acting as wildcards. This is the intended fix; normal
  search terms are unaffected.
- **Worker poll**: behavior is identical with the default 5s; only the
  configuration source changed (env var name is still `WORKER_POLL_SECONDS`
  via pydantic-settings).
- **Re-export**: `escape_like` remains importable from `app.api.access`;
  no call sites changed.

## Follow-ups

- Consider adding `DB_POOL_MIN`/`DB_POOL_MAX` to `.env.example`/docs if one
  is introduced (not in this task's ownership).
- Phase 2 (B1) will split `services/content.py`; the escaped LIKE change
  should be preserved when moving `list_teacher_courses`.
- Phase 5 (S1) may revisit worker polling/queue semantics; keep
  `worker_poll_seconds` as the single source for the analysis worker.
