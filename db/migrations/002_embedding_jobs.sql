-- =============================================================================
-- 002_embedding_jobs.sql — hàng đợi job đồng bộ embedding (RAG ingest).
--
-- Trước đây API schedule ingest bằng FastAPI BackgroundTasks: job mất khi
-- process restart và mỗi replica giữ hàng đợi riêng. Bảng này đưa job vào
-- PostgreSQL để worker riêng (`app.embedding_worker`) claim bằng
-- `FOR UPDATE SKIP LOCKED`; restart không mất việc và nhiều backend replica
-- dùng chung một hàng đợi.
--
-- `target_id` trỏ tới course_versions.id hoặc lesson_versions.id tùy `kind`;
-- không đặt FK vì quan hệ polymorphic.
--
-- schema_generation = 7.
-- =============================================================================

CREATE TABLE embedding_jobs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind           VARCHAR(20) NOT NULL
                   CONSTRAINT embedding_jobs_kind_check
                   CHECK (kind IN ('course_version', 'lesson_version')),
    target_id      UUID NOT NULL,
    include_draft  BOOLEAN NOT NULL DEFAULT false,
    force          BOOLEAN NOT NULL DEFAULT false,
    status         VARCHAR(16) NOT NULL DEFAULT 'pending'
                   CONSTRAINT embedding_jobs_status_check
                   CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    attempts       INTEGER NOT NULL DEFAULT 0
                   CONSTRAINT embedding_jobs_attempts_check
                   CHECK (attempts >= 0),
    max_attempts   INTEGER NOT NULL DEFAULT 3
                   CONSTRAINT embedding_jobs_max_attempts_check
                   CHECK (max_attempts > 0),
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

INSERT INTO app_metadata (key, value) VALUES
    ('schema_generation', '7')
ON CONFLICT (key) DO UPDATE
SET value = EXCLUDED.value, updated_at = now();
