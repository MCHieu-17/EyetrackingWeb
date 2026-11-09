# P5-S1 — DB-backed embedding job queue + worker

> Historical note: `002_embedding_jobs.sql` đã được gộp vào
> `001_baseline.sql` (schema generation 8). Báo cáo này giữ nguyên trạng thái
> lịch sử tại thời điểm thực hiện.

- Branch: `cleanup/p5-s1-embedding-jobs`
- Base: `cleanup/integration` (rebased onto `f251996`)
- Date: 2026-11-09

## Summary

Replaced in-process FastAPI `BackgroundTasks` for embedding/RAG ingest with a
PostgreSQL-backed job queue and a dedicated worker. Jobs now survive process
restarts and are shared by multiple backend replicas; the API only enqueues a
row and returns the same response as before.

1. **Migration `002_embedding_jobs.sql`** — creates `embedding_jobs` with
   `kind` (`course_version` / `lesson_version`), polymorphic `target_id`,
   `include_draft`, `force`, status lifecycle
   (`pending` → `running` → `completed` / `failed`), attempt counters, error,
   and timestamps. Indexes: `(status, created_at)` for claiming and
   `(kind, target_id)` for dedupe. Bumps `app_metadata.schema_generation` to
   `7`.
2. **Model `EmbeddingJob`** — maps the table with the same check constraints
   and indexes; imported in `models/registry.py`.
3. **Service `app/services/embedding_jobs.py`**:
   - `enqueue_course_version` / `enqueue_lesson_version` dedupe against an
     existing `pending`/`running` job with the same
     `kind`/`target_id`/`include_draft`/`force`; otherwise insert and flush
     (caller commits).
   - `claim_next_job` selects the oldest `pending` row with
     `FOR UPDATE SKIP LOCKED`, marks it `running`, sets `started_at`, increments
     `attempts`, and commits.
   - `process_job` opens `SessionLocal`, calls
     `embedding.sync_course_version` / `sync_lesson_version`, and records
     `completed` or `failed`; failures with `attempts < max_attempts` go back to
     `pending`, with `error` truncated to 1000 chars.
   - `process_pending_jobs(limit=1)` claims up to `limit` jobs, releases the
     claim session, then processes them so no DB connection is held during a
     long ingest.
4. **Worker `app/embedding_worker.py`** — uses the shared
   `run_worker_loop` with `settings.embedding_worker_poll_seconds` (new setting,
   default `5.0`) and `process_pending_jobs(limit=1)`.
5. **Routes** — `courses.py` and `lessons.py` no longer take `BackgroundTasks`.
   - Publish 409 branch: mark slides pending, enqueue
     `(include_draft=True, force=True)`, commit, return the identical 409 JSON.
   - Publish success: enqueue `(include_draft=False, force=True)`, commit,
     return the identical `{"ok": true, "courseVersionId": ...}`.
   - Reindex: after `mark_lesson_version_pending`, enqueue
     `(include_draft=True, force=True)`, commit, return the identical
     `{"ok": true, "queued": ...}`.
6. **Schema guard** — `EXPECTED_SCHEMA_GENERATION = "7"` in `main.py`.
7. **Migration test** — expects 2 migrations, `schema_generation=7`, and the
   `embedding_jobs` table.
8. **Compose** — new `embedding-worker` service using the backend `api` image
   target, `python -m app.embedding_worker`, `depends_on` migrate/redis,
   `<<: *backend-env` plus `EMBEDDING_WORKER_POLL_SECONDS`, healthcheck
   disabled, `mem_limit: 2g`, `cpus: 1.0`.
9. **Tests** — `backend/tests/test_embedding_jobs.py` covers enqueue dedupe,
   flag-sensitive dedupe, claim/attempts, success for both kinds, retry then
   terminal failure, and `process_pending_jobs` limit behavior.

## Schema

```sql
CREATE TABLE embedding_jobs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind           VARCHAR(20) NOT NULL
                   CHECK (kind IN ('course_version', 'lesson_version')),
    target_id      UUID NOT NULL,
    include_draft  BOOLEAN NOT NULL DEFAULT false,
    force          BOOLEAN NOT NULL DEFAULT false,
    status         VARCHAR(16) NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    attempts       INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts   INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts > 0),
    error          TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at     TIMESTAMPTZ,
    finished_at    TIMESTAMPTZ,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_embedding_jobs_status_created
    ON embedding_jobs (status, created_at);
CREATE INDEX idx_embedding_jobs_kind_target
    ON embedding_jobs (kind, target_id);
```

`target_id` is polymorphic (`course_versions.id` or `lesson_versions.id`), so
there is intentionally no FK. `force` is passed through to the existing
`sync_*` third parameter, which is `only_pending` (the historical call sites
already passed `True` there).

## Files changed

| File | Change |
|---|---|
| `db/migrations/002_embedding_jobs.sql` | new table, indexes, generation 7 |
| `backend/app/models/embedding_job.py` | new ORM model |
| `backend/app/models/registry.py` | import/export `EmbeddingJob` |
| `backend/app/services/embedding_jobs.py` | new queue service |
| `backend/app/embedding_worker.py` | new worker entrypoint |
| `backend/app/api/routes/courses.py` | enqueue instead of `BackgroundTasks` |
| `backend/app/api/routes/lessons.py` | enqueue instead of `BackgroundTasks` |
| `backend/app/main.py` | `EXPECTED_SCHEMA_GENERATION = "7"` |
| `backend/app/core/config.py` | `embedding_worker_poll_seconds = 5.0` |
| `docker-compose.yml` | new `embedding-worker` service |
| `scripts/test_migrations.sh` | expect 2 migrations / generation 7 / table |
| `backend/tests/test_embedding_jobs.py` | new queue tests |
| `backend/tests/test_health.py` | schema generation assertion 6 → 7 |
| `docs/cleanup/reports/p5-s1-embedding-jobs.md` | this report |

`backend/app/services/embedding.py`, all other models, other routes,
`frontend/**`, `README.md`, and `.env` were not modified. `config.py` and
`test_health.py` are outside the task's file list but were required by task 4
(new setting) and the schema-generation bump (existing assertion).

## Tests run

```text
$ backend/.venv/bin/ruff check backend/app backend/tests
All checks passed!

$ COMPOSE_PROJECT_NAME=eyelearning TEST_DB=eyetracking_test_s1 ./scripts/test_backend.sh
...
[test_backend] chạy pytest
........................................................................ [ 97%]
..                                                                       [100%]
74 passed in 24.44s
[test_backend] OK

$ COMPOSE_PROJECT_NAME=eyelearning ./scripts/test_migrations.sh
...
[test_migrations] kiểm tra schema
[test_migrations] OK

$ COMPOSE_PROJECT_NAME=eyelearning docker compose config >/dev/null
compose config OK
```

74 = 67 existing tests + 7 new `test_embedding_jobs.py` tests.

### Environment note

The worktree has no `.env` (gitignored). A local untracked symlink
`.env -> ../../EyeLearning/.env` was created to run the unmodified scripts, and
commands were run with `COMPOSE_PROJECT_NAME=eyelearning` to target the
already-running stack. The local `eyelearning-migrations:local` image was
rebuilt from this worktree so the one-shot `migrate` service includes
`002_embedding_jobs.sql`; no tracked config was changed for this.

## Risks

- **Stale `running` jobs**: if a worker dies after claiming a job, the row stays
  `running` and is never retried. The task spec did not include stale recovery;
  see follow-ups.
- **Dedupe is best-effort**: without a partial unique index, two concurrent
  enqueues can insert duplicate jobs. Both jobs are idempotent because
  `sync_*` skips slides already `ready`, so the cost is extra work, not
  incorrect data.
- **Enqueue failure now fails the request**: previously scheduling a background
  task could not fail the API call. Enqueue + commit happens before the
  response, so a DB failure returns 500 instead of silently losing the job.
  This is the intended durability trade-off.
- **Cross-replica concurrency**: `embedding._single_flight` is per process, so
  two worker replicas can call the chatbot concurrently. The chatbot serializes
  ingest with its own lock, and DB claiming guarantees each job is processed by
  one worker.
- **`force` naming**: the column is named `force` per the task contract but is
  passed as the existing `only_pending` argument. Renaming would be a schema/API
  change; documented here to avoid confusion.

## Follow-ups

- Add stale-job recovery (requeue `running` rows older than N minutes) in the
  S2 maintenance worker, or in `process_pending_jobs` before claiming.
- Add a partial unique index on
  `(kind, target_id, include_draft, force) WHERE status IN ('pending','running')`
  and handle `ON CONFLICT` for strict dedupe under concurrency.
- Add retention/cleanup for old `completed`/`failed` rows.
- Export queue depth / failure counters for observability (S3).
- Consider renaming `force` to `only_pending` in a future migration if the
  contract allows it.
