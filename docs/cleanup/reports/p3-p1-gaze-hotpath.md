# P3-P1 — Gaze / learning-session hot path

- Branch: `cleanup/p3-p1-gaze-hotpath`
- Base: `cleanup/integration`
- Date: 2026-11-09

## Summary

Removed the eager relationship loads that made every gaze batch (and the
learning-session end/contents endpoints) pull far more rows than needed:

1. **`gaze_ingest._session_for_user`**
   - `LearningSession` is now loaded with
     `select(...).options(raiseload(LearningSession.presentations))` instead of
     `db.get(LearningSession)`. The `lazy="selectin"` presentations query is
     gone.
   - The enrollment check now selects only `Enrollment.student_id` instead of
     `db.get(Enrollment)`. `Enrollment.course` is `lazy="joined"` and `Course`
     eagerly selectin-loads `versions`/`enrollments`, so the old code loaded
     the whole course graph (course, owner, creator, versions, items, modules,
     module items, creator roles) on every batch.
2. **`learning_sessions`**
   - `create_learning_session` loads the enrollment with
     `db.get(Enrollment, ..., options=[raiseload(Enrollment.course)])`.
   - `end_learning_session` and `get_session_contents` share a new
     `_session_for_user` helper that loads the session with
     `raiseload(LearningSession.presentations)` and selects only
     `Enrollment.student_id`.
   - All 404 (missing session), 403 (not the owner / missing enrollment) and
     409 (session already closed) branches are unchanged.

No API path, response shape, status code, auth or CSRF behavior changed.

## Query counts

Measured with `tests.query_counter.count_queries(engine)` around the first
`POST /api/learning-sessions/{id}/gaze-batches` (includes the 2 auth queries
and the 2 INSERTs, which are outside this task's scope).

| Path | Before | After |
|---|---|---|
| Gaze batch (first, 2 samples) | **14** | **9** |
| End learning session (PATCH) | not measured | **6** |

Before (14 statements):

1. auth: `SELECT users`
2. auth: `SELECT user_roles JOIN roles`
3. `SELECT learning_sessions`
4. `SELECT content_presentations` — selectin from `LearningSession.presentations`
5. `SELECT enrollments JOIN courses JOIN teacher_profiles JOIN users JOIN user_profiles` — joined `Enrollment.course` + `Course.owner`/`creator`
6. `SELECT user_roles JOIN roles` — selectin for `Course.creator`
7. `SELECT course_versions` — selectin `Course.versions`
8. `SELECT course_version_items` — selectin `CourseVersion.items`
9. `SELECT course_version_modules` — selectin `CourseVersion.modules`
10. `SELECT course_version_modules JOIN course_version_items` — nested selectin
11. `SELECT gaze_batches` (idempotency lookup)
12. `SELECT max(gaze_batches.batch_no)`
13. `INSERT gaze_batches`
14. `INSERT gaze_samples`

After (9 statements):

1. auth: `SELECT users`
2. auth: `SELECT user_roles JOIN roles`
3. `SELECT learning_sessions` (presentations raiseload)
4. `SELECT enrollments.student_id` only
5. `SELECT content_presentations` (the requested presentation)
6. `SELECT gaze_batches` (idempotency lookup)
7. `SELECT max(gaze_batches.batch_no)`
8. `INSERT gaze_batches`
9. `INSERT gaze_samples`

The remaining 9 are the 2 auth queries, 2 inserts, and 5 queries required by
the endpoint's behavior (session, enrollment owner, presentation, duplicate
check, next batch number). Reaching the PLAN budget of ≤ 5 would require
combining auth/inserts/checks outside this task's ownership.

## Files changed

| File | Change |
|---|---|
| `backend/app/api/routes/gaze_ingest.py` | `_session_for_user`: raiseload presentations, select only enrollment `student_id` |
| `backend/app/api/routes/learning_sessions.py` | raiseload course on enrollment; shared `_session_for_user` for end/contents |
| `backend/tests/test_gaze_ingest.py` | new `test_gaze_batch_query_count` (threshold ≤ 9, prints statements on failure) |
| `backend/tests/test_learning_sessions.py` | new: end/contents happy path + 403/404/409 behavior |
| `docs/cleanup/reports/p3-p1-gaze-hotpath.md` | this report |

No forbidden files (`backend/app/models/**`, `backend/app/services/**`,
other routes, `db/migrations/**`, `frontend/**`, `docker-compose.yml`,
`README.md`, `.env`) were modified.

## Tests run

```text
$ backend/.venv/bin/ruff check backend/app backend/tests
All checks passed!

$ COMPOSE_PROJECT_NAME=eyelearning TEST_DB=eyetracking_test_p1 ./scripts/test_backend.sh
...
[test_backend] chạy pytest
.....................................................                    [100%]
53 passed in 15.44s
[test_backend] OK
```

53 = 50 existing tests + 1 new gaze query-count test + 2 new
learning-session tests.

Focused run:

```text
$ cd backend && TEST_DATABASE_URL=... .venv/bin/pytest -q \
    tests/test_gaze_ingest.py tests/test_learning_sessions.py
4 passed in 3.42s
```

### Environment note

The worktree has no `.env` (gitignored, not copied by
`scripts/worktree_setup.sh`). A local symlink `.env -> ../../EyeLearning/.env`
was created (untracked, not committed). The test script was run with
`COMPOSE_PROJECT_NAME=eyelearning` so `docker compose exec/run` targets the
already-running stack instead of creating a new compose project. No scripts
were modified.

## Risks

- **`raiseload` is a guard**: any future code in these routes that touches
  `session.presentations` or `enrollment.course` will raise
  `InvalidRequestError` instead of silently lazy-loading. If a route really
  needs them, add an explicit `selectinload`/`joinedload` for that query.
- **Query-count test includes auth**: the threshold of 9 covers the 2 auth
  queries and 2 inserts. Adding any query to the request will fail the test;
  that is intentional, but the threshold must be updated deliberately if a
  legitimate query is added.
- **`db.refresh` after commit**: `end_learning_session` still refreshes the
  session row (1 query) but does not reload presentations (verified: 6
  queries total, no `content_presentations` statement).
- **Behavior preserved**: missing session → 404, missing/mismatched
  enrollment → 403, closed session → 409. Covered by the new tests.

## Follow-ups

- P4 harness can measure p95 latency and optionally exclude auth overhead
  from the gaze budget.
- If the ≤ 5 gaze budget is enforced strictly, combine the session +
  enrollment-owner lookup into one outer-join query (would reach 8) and/or
  revisit the auth dependency; both are outside this task's ownership.
- Consider `db.refresh(session, attribute_names=[...])` or dropping the
  refresh in `end_learning_session`/`create_learning_session` to shave one
  more query.
- P2/P3 can apply the same `raiseload` pattern to media/quiz/AOI and
  chat/analysis/metrics access paths.
