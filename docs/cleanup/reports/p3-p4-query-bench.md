# P3-P4 — Query-count harness + benchmark

- Branch: `cleanup/p3-p4-query-bench`
- Base: `cleanup/integration`
- Date: 2026-11-09
- Scope: test/benchmark harness only; **no application code changed**.

## Summary

Added a deterministic query-count regression harness for the hot endpoints that
P1–P3 will optimize, plus a small HTTP benchmark script:

1. `backend/tests/performance/test_query_counts.py` — 4 endpoint-level tests
   using the existing `client`, `create_user`, `seed_course`, `seed_slide` and
   `login` fixtures and the Wave-1 `tests.query_counter.count_queries` helper.
   Each test logs in, performs one warm-up request, then counts SQL statements
   for the measured request and asserts `count <= baseline`.
2. `backend/tests/performance/conftest.py` — registers the `performance` marker
   when the directory is collected (avoids `PytestUnknownMarkWarning` without
   touching the shared `backend/pytest.ini`).
3. `scripts/bench.sh` — optional `BASE_URL` + `PATH`; uses `hey` if installed,
   otherwise `wrk`, otherwise prints install instructions and exits 0. Runs a
   warm-up and a measured run (default 200 requests / 10 concurrency) and prints
   p95 (hey) or p90/p99 (wrk, which does not expose p95).
4. This report.

The tests are marked `pytest.mark.performance` and run as part of the normal
backend suite (38 tests total: 34 existing + 4 new).

## Baseline query counts

Measured on `cleanup/integration` (2026-11-09) against the migrated test DB.
Counts include the 2 auth queries (`users` + `user_roles`) emitted by
`get_current_user` for every authenticated request.

| Endpoint | Baseline | Test constant | PLAN target | Notes |
|---|---:|---:|---:|---|
| `GET /teacher/courses` | **6** | `TEACHER_COURSES_MAX_QUERIES = 6` | ≤ 10 | Already within target |
| `GET /teacher/courses/{course_id}/students` | **9** | `COURSE_STUDENTS_MAX_QUERIES = 9` | ≤ 10 | Seeds one slide to exercise the metrics/mastery path |
| `POST /api/learning-sessions/{session_id}/gaze-batches` | **14** | `GAZE_BATCH_MAX_QUERIES = 14` | ≤ 5 | Heavy enrollment/course graph load (P1 target) |
| `GET /media/assets/{asset_id}/file` | **17** | `MEDIA_ASSET_MAX_QUERIES = 17` | ≤ 5 | Heavy `db.get(Course)` graph load (P2 target) |

### Query breakdown

`GET /teacher/courses` (6):

1. auth `users`
2. auth `user_roles`
3. course list + item-count subquery
4. `enrollment_counts`
5. `attention_avg_by_course`
6. `session_counts_by_course`

`GET /teacher/courses/{id}/students` (9, with one slide):

1–2. auth `users`, `user_roles`
3. `get_viewable_course` (`courses`)
4. published `course_versions.id`
5. `course_version_items` + `lessons`
6. `enrollments` + `users` + profiles
7. last-active `learning_sessions`
8. `lesson_version_slides`
9. `presentation_metrics` aggregate (mastery)

`POST /api/learning-sessions/{id}/gaze-batches` (14):

1–2. auth `users`, `user_roles`
3. `_session_for_user` → `learning_sessions`
4. presentation `content_presentations`
5. `_session_for_user` → `enrollments` (eager-loads course graph)
6. `course_versions`
7. `user_roles` (course owner)
8. `course_version_modules`
9. `course_version_items`
10. `course_version_modules` (second eager load)
11. existing `gaze_batches` lookup
12. `max(batch_no)`
13. `INSERT gaze_batches`
14. `INSERT gaze_samples`

`GET /media/assets/{id}/file` (17):

1–2. auth `users`, `user_roles`
3. `media_assets`
4. `db.get(Course)` (`courses`)
5–15. course graph eager loads (`course_versions`, `enrollments`,
   `user_roles`, `course_version_modules`, `course_version_items`, repeated)
16. enrollment check
17. `_asset_published` (`slide_versions` join)

The 14/17 counts confirm the P1/P2 targets: the gaze and media paths still load
the full course graph even though they only need a few columns.

## How to run

### Query-count tests

```bash
# Full backend suite (creates/drops TEST_DB via docker compose)
TEST_DB=eyetracking_test_p4 ./scripts/test_backend.sh

# Only the performance tests (DB must already be migrated)
cd backend
TEST_DATABASE_URL="postgresql+asyncpg://postgres:change-me@127.0.0.1:5435/eyetracking_test_p4" \
    .venv/bin/pytest -q tests/performance
```

The worktree has no `.env` (gitignored). For local runs, copy/symlink the main
repo `.env` and export `COMPOSE_PROJECT_NAME=eyelearning` so `docker compose`
targets the already-running stack:

```bash
cp ../../EyeLearning/.env .env   # or ln -s
COMPOSE_PROJECT_NAME=eyelearning TEST_DB=eyetracking_test_p4 ./scripts/test_backend.sh
```

### HTTP benchmark

```bash
./scripts/bench.sh                                  # http://localhost:8001/health
./scripts/bench.sh http://localhost:8001 /health
AUTH_HEADER="Authorization: Bearer $TOKEN" \
    ./scripts/bench.sh http://localhost:8001 /teacher/courses
```

Environment overrides: `REQUESTS` (200), `CONCURRENCY` (10),
`WARMUP_REQUESTS` (20), `DURATION`/`WARMUP_DURATION` (wrk only), `AUTH_HEADER`.
The script does not require auth; authenticated endpoints need `AUTH_HEADER`.
Note: the backend has no `/api` prefix for teacher routes; through nginx the
public path is `/api/teacher/...`, but direct calls to port 8001 use
`/teacher/...`.

## Tests run

```text
$ backend/.venv/bin/ruff check backend/tests
All checks passed!

$ TEST_DB=eyetracking_test_p4 ./scripts/test_backend.sh
...
38 passed in 16.01s
[test_backend] OK
```

38 = 34 existing tests + 4 new performance tests. The performance tests alone
run in ~3s.

## Risks

- **Baseline is data-shape dependent.** The students test seeds one slide so the
  metrics query is exercised; other shapes (no items, no enrollments, no slides)
  return earlier with fewer queries. The constants lock the seeded shape only.
- **Auth queries are included.** If auth is optimized later, all four baselines
  drop by up to 2; P1–P3 should lower the constants accordingly.
- **Exact baselines are intentionally tight.** Any new query in these paths
  fails the test. This is the point, but unrelated features that legitimately
  add a query must update the constant and this report.
- **`wrk` fallback does not report p95.** It prints p90/p99 and says so; use
  `hey` when exact p95 is required.
- **Benchmark results are environment-dependent** (CPU, DB pool, Redis, network).
  Compare before/after on the same machine and stack; do not compare across
  machines.
- **Marker registration lives in the performance conftest.** It works for both
  `pytest tests/performance` and the full suite, but the canonical place is
  `backend/pytest.ini` (owned by A4).

## Follow-ups

1. **P1** lowers `GAZE_BATCH_MAX_QUERIES` after removing the enrollment/course
   graph load; **P2** lowers `MEDIA_ASSET_MAX_QUERIES` after removing the heavy
   `db.get(Course)`; **P3** re-checks `COURSE_STUDENTS_MAX_QUERIES` after the
   metrics changes.
2. Register the `performance` marker in `backend/pytest.ini` and remove the
   local conftest hook.
3. Add query-count tests for chat/analysis endpoints once P3 lands.
4. Wire `pytest -m performance` into `scripts/check.sh --full` (or a separate
   perf gate) so regressions fail CI.
5. Capture `hey` p95 before/after for the same endpoints and record them in
   `STATUS.md` alongside the query counts.

## Files changed

| File | Change |
|---|---|
| `backend/tests/performance/__init__.py` | New package marker |
| `backend/tests/performance/conftest.py` | New: register `performance` marker |
| `backend/tests/performance/test_query_counts.py` | New: 4 query-count tests + baselines |
| `scripts/bench.sh` | New: hey/wrk benchmark wrapper |
| `docs/cleanup/reports/p3-p4-query-bench.md` | This report |

No application code, existing tests, `backend/tests/conftest.py`,
`backend/tests/query_counter.py`, migrations, frontend, compose, README or
`.env` were modified.
