-- =============================================================================
-- 001_baseline.sql — schema đích duy nhất của EyeLearning (Phase 1)
--
-- Baseline được dựng từ database rỗng. Không chứa dữ liệu mẫu, không chứa
-- migration lịch sử. Runner bọc mỗi file trong một transaction riêng.
--
-- Thứ tự: identity/auth → media → content/version → quiz → calibration/session
--         → AOI/layout → gaze → analysis/metrics → chat → metadata → view/trigger.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 0) Extensions + helper
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- unaccent() không immutable nên không dùng trực tiếp trong generated column.
CREATE OR REPLACE FUNCTION immutable_unaccent(text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
STRICT
AS $$
    SELECT translate(unaccent('unaccent', $1), 'đĐ', 'dD');
$$;

-- ---------------------------------------------------------------------------
-- 1) Identity / auth
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email               VARCHAR(255) NOT NULL,
    password_hash       VARCHAR(255),
    status              VARCHAR(20) NOT NULL DEFAULT 'active'
                        CONSTRAINT users_status_check
                        CHECK (status IN ('active', 'suspended', 'banned')),
    last_login_at       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ,
    must_change_password BOOLEAN NOT NULL DEFAULT false
);
CREATE UNIQUE INDEX ux_users_email_lower ON users (lower(email));

CREATE TABLE roles (
    id      SMALLSERIAL PRIMARY KEY,
    code    VARCHAR(30) NOT NULL UNIQUE,
    label   VARCHAR(100)
);

CREATE TABLE user_roles (
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id     SMALLINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    granted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, role_id)
);
CREATE INDEX idx_user_roles_role ON user_roles (role_id);

CREATE TABLE auth_sessions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash  VARCHAR(255) NOT NULL,
    user_agent          TEXT,
    ip_address          INET,
    expires_at          TIMESTAMPTZ NOT NULL,
    revoked_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_auth_sessions_refresh_token_hash
    ON auth_sessions (refresh_token_hash);
CREATE INDEX idx_auth_sessions_user ON auth_sessions (user_id);

CREATE TABLE user_profiles (
    user_id         UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    full_name       VARCHAR(150) NOT NULL,
    date_of_birth   DATE,
    gender          VARCHAR(20)
                    CONSTRAINT user_profiles_gender_check
                    CHECK (gender IN ('male', 'female', 'other')),
    phone           VARCHAR(20),
    avatar_url      TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE student_profiles (
    user_id         UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    student_code    VARCHAR(30) NOT NULL UNIQUE,
    program         VARCHAR(200)
);

CREATE TABLE teacher_profiles (
    user_id         UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    teacher_code    VARCHAR(30) NOT NULL UNIQUE,
    department      VARCHAR(150)
);

-- ---------------------------------------------------------------------------
-- 2) Courses (identity) + enrollment
-- ---------------------------------------------------------------------------
CREATE TABLE courses (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id              UUID NOT NULL REFERENCES teacher_profiles(user_id) ON DELETE RESTRICT,
    created_by            UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    archived_at           TIMESTAMPTZ,
    show_gaze_dot         BOOLEAN NOT NULL DEFAULT false,
    require_calibration   BOOLEAN NOT NULL DEFAULT true,
    published_version_id  UUID,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_courses_owner ON courses (owner_id);
CREATE INDEX idx_courses_archived ON courses (archived_at);

CREATE TABLE course_teachers (
    course_id    UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    teacher_id   UUID NOT NULL REFERENCES teacher_profiles(user_id) ON DELETE CASCADE,
    assigned_by  UUID REFERENCES users(id) ON DELETE SET NULL,
    assigned_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (course_id, teacher_id)
);
CREATE INDEX idx_course_teachers_teacher ON course_teachers (teacher_id);

CREATE TABLE enrollments (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id    UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    student_id   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    enrolled_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    status       VARCHAR(30) NOT NULL DEFAULT 'active'
                 CONSTRAINT enrollments_status_check
                 CHECK (status IN ('active', 'completed', 'dropped')),
    UNIQUE (course_id, student_id)
);
CREATE INDEX idx_enrollments_student ON enrollments (student_id);

-- ---------------------------------------------------------------------------
-- 3) Media assets
-- ---------------------------------------------------------------------------
CREATE TABLE media_assets (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id         UUID NOT NULL REFERENCES courses(id) ON DELETE RESTRICT,
    storage_backend   VARCHAR(16) NOT NULL
                      CONSTRAINT media_assets_storage_backend_check
                      CHECK (storage_backend IN ('local', 'r2')),
    object_key        TEXT NOT NULL,
    sha256            CHAR(64) NOT NULL
                      CONSTRAINT media_assets_sha256_check
                      CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    mime_type         VARCHAR(127) NOT NULL,
    byte_size         BIGINT NOT NULL
                      CONSTRAINT media_assets_byte_size_check
                      CHECK (byte_size >= 0),
    image_width       INTEGER
                      CONSTRAINT media_assets_image_width_check
                      CHECK (image_width > 0),
    image_height      INTEGER
                      CONSTRAINT media_assets_image_height_check
                      CHECK (image_height > 0),
    state             VARCHAR(16) NOT NULL DEFAULT 'staging'
                      CONSTRAINT media_assets_state_check
                      CHECK (state IN ('staging', 'ready', 'failed', 'deleted')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (course_id, sha256),
    UNIQUE (storage_backend, object_key)
);
CREATE INDEX idx_media_assets_course ON media_assets (course_id);
CREATE INDEX idx_media_assets_state ON media_assets (state);

-- ---------------------------------------------------------------------------
-- 4) Course versions / modules / lessons / slides
-- ---------------------------------------------------------------------------
CREATE TABLE course_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id           UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    version_no          INTEGER NOT NULL
                        CONSTRAINT course_versions_version_no_check
                        CHECK (version_no > 0),
    state               VARCHAR(16) NOT NULL DEFAULT 'draft'
                        CONSTRAINT course_versions_state_check
                        CHECK (state IN ('draft', 'published', 'archived')),
    generation          INTEGER NOT NULL DEFAULT 1
                        CONSTRAINT course_versions_generation_check
                        CHECK (generation > 0),
    title               VARCHAR(255) NOT NULL,
    description         TEXT,
    thumbnail_asset_id  UUID REFERENCES media_assets(id) ON DELETE RESTRICT,
    created_by          UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at        TIMESTAMPTZ,
    published_by        UUID REFERENCES users(id) ON DELETE RESTRICT,
    UNIQUE (course_id, version_no)
);
CREATE UNIQUE INDEX ux_course_versions_one_draft
    ON course_versions (course_id) WHERE state = 'draft';
CREATE INDEX idx_course_versions_course_state
    ON course_versions (course_id, state);

CREATE TABLE course_version_modules (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_version_id  UUID NOT NULL REFERENCES course_versions(id) ON DELETE CASCADE,
    module_key         UUID NOT NULL DEFAULT gen_random_uuid(),
    title              VARCHAR(255) NOT NULL,
    position           INTEGER NOT NULL
                       CONSTRAINT course_version_modules_position_check
                       CHECK (position >= 0),
    UNIQUE (course_version_id, position),
    UNIQUE (course_version_id, module_key),
    UNIQUE (id, course_version_id)
);

CREATE TABLE lessons (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id   UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    kind        VARCHAR(10) NOT NULL
                CONSTRAINT lessons_kind_check
                CHECK (kind IN ('lesson', 'quiz')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_lessons_course_kind ON lessons (course_id, kind);

CREATE TABLE lesson_versions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_id     UUID NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    version_no    INTEGER NOT NULL
                  CONSTRAINT lesson_versions_version_no_check
                  CHECK (version_no > 0),
    state         VARCHAR(16) NOT NULL DEFAULT 'draft'
                  CONSTRAINT lesson_versions_state_check
                  CHECK (state IN ('draft', 'published', 'archived')),
    title         VARCHAR(255) NOT NULL,
    created_by    UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at  TIMESTAMPTZ,
    published_by  UUID REFERENCES users(id) ON DELETE RESTRICT,
    UNIQUE (lesson_id, version_no),
    UNIQUE (id, lesson_id)
);
CREATE UNIQUE INDEX ux_lesson_versions_one_draft
    ON lesson_versions (lesson_id) WHERE state = 'draft';
CREATE INDEX idx_lesson_versions_lesson_state
    ON lesson_versions (lesson_id, state);

CREATE TABLE course_version_items (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_version_id  UUID NOT NULL REFERENCES course_versions(id) ON DELETE CASCADE,
    module_id          UUID NOT NULL,
    lesson_id          UUID NOT NULL REFERENCES lessons(id) ON DELETE RESTRICT,
    lesson_version_id  UUID NOT NULL,
    position           INTEGER NOT NULL
                       CONSTRAINT course_version_items_position_check
                       CHECK (position >= 0),
    UNIQUE (course_version_id, position),
    UNIQUE (course_version_id, lesson_id),
    UNIQUE (id, course_version_id),
    FOREIGN KEY (module_id, course_version_id)
        REFERENCES course_version_modules(id, course_version_id) ON DELETE CASCADE,
    FOREIGN KEY (lesson_version_id, lesson_id)
        REFERENCES lesson_versions(id, lesson_id) ON DELETE RESTRICT
);
CREATE INDEX idx_course_version_items_lesson
    ON course_version_items (lesson_id);
CREATE INDEX idx_course_version_items_lesson_version
    ON course_version_items (lesson_version_id);

CREATE TABLE slides (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_id   UUID NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_slides_lesson ON slides (lesson_id);

CREATE TABLE slide_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slide_id            UUID NOT NULL REFERENCES slides(id) ON DELETE CASCADE,
    revision_no         INTEGER NOT NULL
                        CONSTRAINT slide_versions_revision_no_check
                        CHECK (revision_no > 0),
    image_asset_id      UUID NOT NULL REFERENCES media_assets(id) ON DELETE RESTRICT,
    source_pdf_asset_id UUID REFERENCES media_assets(id) ON DELETE RESTRICT,
    source_page         INTEGER
                        CONSTRAINT slide_versions_source_page_check
                        CHECK (source_page > 0),
    render_metadata     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by          UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (slide_id, revision_no),
    UNIQUE (id, slide_id)
);
CREATE INDEX idx_slide_versions_slide ON slide_versions (slide_id);
CREATE INDEX idx_slide_versions_image_asset ON slide_versions (image_asset_id);

CREATE TABLE lesson_version_slides (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_version_id  UUID NOT NULL REFERENCES lesson_versions(id) ON DELETE CASCADE,
    slide_id           UUID NOT NULL,
    slide_version_id   UUID NOT NULL,
    position           INTEGER NOT NULL
                       CONSTRAINT lesson_version_slides_position_check
                       CHECK (position >= 0),
    title              VARCHAR(255) NOT NULL DEFAULT '',
    is_key             BOOLEAN NOT NULL DEFAULT false,
    UNIQUE (lesson_version_id, position),
    UNIQUE (lesson_version_id, slide_id),
    UNIQUE (id, lesson_version_id),
    FOREIGN KEY (slide_version_id, slide_id)
        REFERENCES slide_versions(id, slide_id) ON DELETE RESTRICT
);
CREATE INDEX idx_lesson_version_slides_slide_version
    ON lesson_version_slides (slide_version_id);

CREATE TABLE slide_documents (
    slide_version_id  UUID PRIMARY KEY REFERENCES slide_versions(id) ON DELETE CASCADE,
    pipeline_version  VARCHAR(64) NOT NULL,
    model_version     VARCHAR(64) NOT NULL,
    transcript        TEXT NOT NULL DEFAULT '',
    -- NULL khi pending/failed: chỉ ghi vector sau khi ingest thành công.
    embedding         VECTOR(1024),
    content_tsv       TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('simple', immutable_unaccent(transcript))
    ) STORED,
    ingestion_state   VARCHAR(16) NOT NULL DEFAULT 'pending'
                      CONSTRAINT slide_documents_ingestion_state_check
                      CHECK (ingestion_state IN ('pending', 'ready', 'failed')),
    ingestion_error   TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_slide_documents_state ON slide_documents (ingestion_state);
CREATE INDEX idx_slide_documents_tsv ON slide_documents USING gin (content_tsv);
CREATE INDEX idx_slide_documents_hnsw ON slide_documents
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE TABLE content_audit_events (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id           UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    course_id          UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    course_version_id  UUID REFERENCES course_versions(id) ON DELETE SET NULL,
    action             VARCHAR(16) NOT NULL
                       CONSTRAINT content_audit_events_action_check
                       CHECK (action IN ('publish', 'archive', 'restore')),
    request_id         UUID,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_content_audit_course
    ON content_audit_events (course_id, created_at);

-- ---------------------------------------------------------------------------
-- 5) Quiz
-- ---------------------------------------------------------------------------
CREATE TABLE quiz_specs (
    lesson_version_id  UUID PRIMARY KEY REFERENCES lesson_versions(id) ON DELETE CASCADE,
    instructions       TEXT NOT NULL DEFAULT '',
    duration_minutes   INTEGER NOT NULL
                       CONSTRAINT quiz_specs_duration_minutes_check
                       CHECK (duration_minutes > 0),
    due_at             TIMESTAMPTZ,
    allow_retry        BOOLEAN NOT NULL DEFAULT false,
    allow_chatbot      BOOLEAN NOT NULL DEFAULT false,
    questions          JSONB NOT NULL DEFAULT '[]'::jsonb
                       CONSTRAINT quiz_specs_questions_array_check
                       CHECK (jsonb_typeof(questions) = 'array'),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE quiz_attempts (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enrollment_id          UUID NOT NULL REFERENCES enrollments(id) ON DELETE CASCADE,
    course_version_item_id UUID NOT NULL REFERENCES course_version_items(id) ON DELETE RESTRICT,
    lesson_id              UUID NOT NULL REFERENCES lessons(id) ON DELETE RESTRICT,
    attempt_no             INTEGER NOT NULL
                           CONSTRAINT quiz_attempts_attempt_no_check
                           CHECK (attempt_no > 0),
    status                 VARCHAR(16) NOT NULL DEFAULT 'in_progress'
                           CONSTRAINT quiz_attempts_status_check
                           CHECK (status IN ('in_progress', 'submitted', 'expired')),
    started_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at             TIMESTAMPTZ NOT NULL,
    submitted_at           TIMESTAMPTZ,
    answers                JSONB NOT NULL DEFAULT '{}'::jsonb
                           CONSTRAINT quiz_attempts_answers_object_check
                           CHECK (jsonb_typeof(answers) = 'object'),
    grading                JSONB NOT NULL DEFAULT '{}'::jsonb
                           CONSTRAINT quiz_attempts_grading_object_check
                           CHECK (jsonb_typeof(grading) = 'object'),
    score                  REAL
                           CONSTRAINT quiz_attempts_score_check
                           CHECK (score >= 0),
    max_score              REAL
                           CONSTRAINT quiz_attempts_max_score_check
                           CHECK (max_score >= 0),
    UNIQUE (enrollment_id, lesson_id, attempt_no)
);
CREATE UNIQUE INDEX ux_quiz_attempts_one_in_progress
    ON quiz_attempts (enrollment_id, lesson_id) WHERE status = 'in_progress';
CREATE INDEX idx_quiz_attempts_enrollment
    ON quiz_attempts (enrollment_id, lesson_id, attempt_no);
CREATE INDEX idx_quiz_attempts_item
    ON quiz_attempts (course_version_item_id);

-- ---------------------------------------------------------------------------
-- 6) Calibration
-- ---------------------------------------------------------------------------
CREATE TABLE devices (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id               UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    fingerprint            VARCHAR(255) NOT NULL,
    current_calibration_id UUID,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (owner_id, fingerprint)
);
CREATE INDEX idx_devices_owner ON devices (owner_id);

CREATE TABLE calibrations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id           UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    model_ubj           BYTEA NOT NULL,
    model_hash          CHAR(64) NOT NULL
                        CONSTRAINT calibrations_model_hash_check
                        CHECK (model_hash ~ '^[0-9a-f]{64}$'),
    model_version       VARCHAR(64) NOT NULL,
    mae_px              REAL
                        CONSTRAINT calibrations_mae_check
                        CHECK (mae_px >= 0),
    viewport_width_px   INTEGER NOT NULL
                        CONSTRAINT calibrations_viewport_width_check
                        CHECK (viewport_width_px > 0),
    viewport_height_px  INTEGER NOT NULL
                        CONSTRAINT calibrations_viewport_height_check
                        CHECK (viewport_height_px > 0),
    device_pixel_ratio  REAL NOT NULL
                        CONSTRAINT calibrations_dpr_check
                        CHECK (device_pixel_ratio > 0),
    config              JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_calibrations_device
    ON calibrations (device_id, created_at);

CREATE TABLE calibration_settings (
    id          SMALLINT PRIMARY KEY DEFAULT 1
                CONSTRAINT calibration_settings_single_row_check
                CHECK (id = 1),
    enabled     BOOLEAN NOT NULL DEFAULT true,
    threshold   REAL NOT NULL DEFAULT 0.12
                CONSTRAINT calibration_settings_threshold_check
                CHECK (threshold BETWEEN 0.01 AND 0.30),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by  UUID REFERENCES users(id) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------------
-- 7) Learning sessions / presentations
-- ---------------------------------------------------------------------------
CREATE TABLE learning_sessions (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enrollment_id          UUID NOT NULL REFERENCES enrollments(id) ON DELETE CASCADE,
    course_version_item_id UUID NOT NULL REFERENCES course_version_items(id) ON DELETE RESTRICT,
    quiz_attempt_id        UUID REFERENCES quiz_attempts(id) ON DELETE SET NULL,
    calibration_id         UUID REFERENCES calibrations(id) ON DELETE RESTRICT,
    pipeline_version       VARCHAR(64) NOT NULL,
    config                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    tracking_consent       BOOLEAN NOT NULL DEFAULT true,
    status                 VARCHAR(16) NOT NULL DEFAULT 'in_progress'
                           CONSTRAINT learning_sessions_status_check
                           CHECK (status IN ('in_progress', 'completed', 'aborted', 'expired')),
    started_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at               TIMESTAMPTZ,
    expires_at             TIMESTAMPTZ NOT NULL,
    clock_uncertainty_ms   INTEGER
                           CONSTRAINT learning_sessions_clock_uncertainty_check
                           CHECK (clock_uncertainty_ms >= 0)
);
CREATE INDEX idx_learning_sessions_enrollment
    ON learning_sessions (enrollment_id, started_at);
CREATE INDEX idx_learning_sessions_item
    ON learning_sessions (course_version_item_id);
CREATE INDEX idx_learning_sessions_status
    ON learning_sessions (status);

CREATE TABLE content_presentations (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id               UUID NOT NULL REFERENCES learning_sessions(id) ON DELETE CASCADE,
    lesson_version_slide_id  UUID REFERENCES lesson_version_slides(id) ON DELETE RESTRICT,
    surface                  VARCHAR(16) NOT NULL
                             CONSTRAINT content_presentations_surface_check
                             CHECK (surface IN ('lesson', 'quiz')),
    sequence_no              INTEGER NOT NULL
                             CONSTRAINT content_presentations_sequence_check
                             CHECK (sequence_no >= 0),
    started_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at                 TIMESTAMPTZ,
    UNIQUE (session_id, sequence_no),
    UNIQUE (id, session_id)
);
CREATE INDEX idx_content_presentations_session
    ON content_presentations (session_id, started_at);

-- ---------------------------------------------------------------------------
-- 8) AOI sets / definitions / layout
-- ---------------------------------------------------------------------------
CREATE TABLE aoi_sets (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope              VARCHAR(16) NOT NULL
                       CONSTRAINT aoi_sets_scope_check
                       CHECK (scope IN ('slide', 'ui')),
    slide_version_id   UUID REFERENCES slide_versions(id) ON DELETE CASCADE,
    ui_schema_version  VARCHAR(64),
    revision           INTEGER NOT NULL
                       CONSTRAINT aoi_sets_revision_check
                       CHECK (revision > 0),
    state              VARCHAR(16) NOT NULL DEFAULT 'draft'
                       CONSTRAINT aoi_sets_state_check
                       CHECK (state IN ('draft', 'published', 'archived')),
    created_by         UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at       TIMESTAMPTZ,
    CONSTRAINT aoi_sets_slide_scope_check
        CHECK ((scope = 'slide') = (slide_version_id IS NOT NULL)),
    CONSTRAINT aoi_sets_ui_scope_check
        CHECK ((scope = 'ui') = (ui_schema_version IS NOT NULL))
);
CREATE UNIQUE INDEX ux_aoi_sets_slide_revision
    ON aoi_sets (slide_version_id, revision) WHERE slide_version_id IS NOT NULL;
CREATE UNIQUE INDEX ux_aoi_sets_ui_revision
    ON aoi_sets (ui_schema_version, revision) WHERE ui_schema_version IS NOT NULL;
CREATE UNIQUE INDEX ux_aoi_sets_one_published_slide
    ON aoi_sets (slide_version_id)
    WHERE state = 'published' AND slide_version_id IS NOT NULL;
CREATE UNIQUE INDEX ux_aoi_sets_one_published_ui
    ON aoi_sets (ui_schema_version)
    WHERE state = 'published' AND ui_schema_version IS NOT NULL;

CREATE TABLE aoi_definitions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aoi_set_id  UUID NOT NULL REFERENCES aoi_sets(id) ON DELETE CASCADE,
    code        VARCHAR(64) NOT NULL,
    name        VARCHAR(100) NOT NULL,
    parent_id   UUID REFERENCES aoi_definitions(id) ON DELETE SET NULL,
    geometry    JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (aoi_set_id, code)
);
CREATE INDEX idx_aoi_definitions_set ON aoi_definitions (aoi_set_id);
CREATE INDEX idx_aoi_definitions_parent ON aoi_definitions (parent_id);

CREATE TABLE aoi_layout_snapshots (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    presentation_id   UUID NOT NULL REFERENCES content_presentations(id) ON DELETE CASCADE,
    ui_aoi_set_id     UUID REFERENCES aoi_sets(id) ON DELETE RESTRICT,
    captured_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    sequence_no       BIGINT NOT NULL
                      CONSTRAINT aoi_layout_snapshots_sequence_check
                      CHECK (sequence_no >= 0),
    layout_generation INTEGER NOT NULL
                      CONSTRAINT aoi_layout_snapshots_generation_check
                      CHECK (layout_generation >= 0),
    image_transform   JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (presentation_id, layout_generation)
);
CREATE INDEX idx_aoi_layout_snapshots_presentation
    ON aoi_layout_snapshots (presentation_id, captured_at);

CREATE TABLE aoi_layout_rects (
    id             BIGSERIAL PRIMARY KEY,
    snapshot_id    UUID NOT NULL REFERENCES aoi_layout_snapshots(id) ON DELETE CASCADE,
    semantic_code  VARCHAR(64) NOT NULL,
    element_key    VARCHAR(128) NOT NULL DEFAULT '',
    x_min          REAL NOT NULL,
    y_min          REAL NOT NULL,
    x_max          REAL NOT NULL,
    y_max          REAL NOT NULL,
    CONSTRAINT aoi_layout_rects_order_check
        CHECK (x_min < x_max AND y_min < y_max),
    CONSTRAINT aoi_layout_rects_bounds_check
        CHECK (x_min > -10 AND x_max < 10 AND y_min > -10 AND y_max < 10)
);
CREATE INDEX idx_aoi_layout_rects_snapshot
    ON aoi_layout_rects (snapshot_id);
CREATE INDEX idx_aoi_layout_rects_code
    ON aoi_layout_rects (semantic_code);

-- ---------------------------------------------------------------------------
-- 9) Gaze batches / samples (partitioned)
-- ---------------------------------------------------------------------------
CREATE TABLE gaze_batches (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id        UUID NOT NULL REFERENCES learning_sessions(id) ON DELETE CASCADE,
    presentation_id   UUID NOT NULL,
    layout_snapshot_id UUID REFERENCES aoi_layout_snapshots(id) ON DELETE SET NULL,
    batch_id          UUID NOT NULL,
    batch_no          INTEGER NOT NULL
                      CONSTRAINT gaze_batches_batch_no_check
                      CHECK (batch_no >= 0),
    sequence_start    BIGINT NOT NULL
                      CONSTRAINT gaze_batches_sequence_start_check
                      CHECK (sequence_start >= 0),
    sequence_end      BIGINT NOT NULL
                      CONSTRAINT gaze_batches_sequence_range_check
                      CHECK (sequence_end >= sequence_start),
    payload_hash      CHAR(64) NOT NULL
                      CONSTRAINT gaze_batches_payload_hash_check
                      CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    received_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    received_count    INTEGER NOT NULL DEFAULT 0
                      CONSTRAINT gaze_batches_received_count_check
                      CHECK (received_count >= 0),
    stored_count      INTEGER NOT NULL DEFAULT 0
                      CONSTRAINT gaze_batches_stored_count_check
                      CHECK (stored_count >= 0),
    duplicate_count   INTEGER NOT NULL DEFAULT 0
                      CONSTRAINT gaze_batches_duplicate_count_check
                      CHECK (duplicate_count >= 0),
    rejected_count    INTEGER NOT NULL DEFAULT 0
                      CONSTRAINT gaze_batches_rejected_count_check
                      CHECK (rejected_count >= 0),
    UNIQUE (session_id, batch_id),
    UNIQUE (session_id, batch_no),
    UNIQUE (id, session_id),
    FOREIGN KEY (presentation_id, session_id)
        REFERENCES content_presentations(id, session_id) ON DELETE CASCADE
);
CREATE INDEX idx_gaze_batches_session
    ON gaze_batches (session_id, batch_no);
CREATE INDEX idx_gaze_batches_presentation
    ON gaze_batches (presentation_id);

CREATE TABLE gaze_samples (
    id                    BIGSERIAL,
    session_id            UUID NOT NULL,
    batch_id              UUID NOT NULL,
    sequence              BIGINT NOT NULL
                          CONSTRAINT gaze_samples_sequence_check
                          CHECK (sequence >= 0),
    capture_monotonic_ns  BIGINT NOT NULL
                          CONSTRAINT gaze_samples_capture_monotonic_check
                          CHECK (capture_monotonic_ns >= 0),
    event_time            TIMESTAMPTZ NOT NULL,
    viewport_x            REAL,
    viewport_y            REAL,
    status                VARCHAR(16) NOT NULL
                          CONSTRAINT gaze_samples_status_check
                          CHECK (status IN ('ok', 'no_face', 'error', 'offscreen')),
    quality_flags         JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (id, event_time),
    FOREIGN KEY (batch_id, session_id)
        REFERENCES gaze_batches(id, session_id) ON DELETE CASCADE,
    CONSTRAINT gaze_samples_status_coords_check CHECK (
        (status = 'ok' AND viewport_x IS NOT NULL AND viewport_y IS NOT NULL)
        OR (status <> 'ok' AND viewport_x IS NULL AND viewport_y IS NULL)
    ),
    CONSTRAINT gaze_samples_viewport_x_check
        CHECK (viewport_x IS NULL OR (viewport_x > -100 AND viewport_x < 100)),
    CONSTRAINT gaze_samples_viewport_y_check
        CHECK (viewport_y IS NULL OR (viewport_y > -100 AND viewport_y < 100))
) PARTITION BY RANGE (event_time);

CREATE TABLE gaze_samples_default PARTITION OF gaze_samples DEFAULT;

CREATE OR REPLACE FUNCTION create_gaze_sample_partitions(months_ahead INT DEFAULT 3)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
    start_date DATE := date_trunc('month', CURRENT_DATE);
    d          DATE;
    part_name  TEXT;
    created    INT := 0;
BEGIN
    FOR i IN -1..months_ahead LOOP
        d := start_date + make_interval(months => i);
        part_name := 'gaze_samples_' || to_char(d, 'YYYY_MM');
        IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = part_name) THEN
            EXECUTE format(
                'CREATE TABLE %I PARTITION OF gaze_samples
                 FOR VALUES FROM (%L) TO (%L)
                 WITH (fillfactor = 90)',
                part_name, d, d + INTERVAL '1 month'
            );
            created := created + 1;
        END IF;
    END LOOP;
    RETURN created;
END;
$$;

SELECT create_gaze_sample_partitions(3);

CREATE INDEX idx_gaze_samples_session
    ON gaze_samples (session_id, event_time);
CREATE INDEX idx_gaze_samples_batch
    ON gaze_samples (batch_id, event_time);

-- ---------------------------------------------------------------------------
-- 10) Analysis / metrics
-- ---------------------------------------------------------------------------
CREATE TABLE analysis_runs (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id         UUID NOT NULL REFERENCES learning_sessions(id) ON DELETE CASCADE,
    aoi_set_id         UUID NOT NULL REFERENCES aoi_sets(id) ON DELETE RESTRICT,
    from_time          TIMESTAMPTZ NOT NULL,
    to_time            TIMESTAMPTZ NOT NULL,
    batch_watermark    UUID REFERENCES gaze_batches(id) ON DELETE SET NULL,
    algorithm_version  VARCHAR(64) NOT NULL,
    config             JSONB NOT NULL DEFAULT '{}'::jsonb,
    status             VARCHAR(16) NOT NULL DEFAULT 'pending'
                       CONSTRAINT analysis_runs_status_check
                       CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    error              TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at       TIMESTAMPTZ,
    CONSTRAINT analysis_runs_time_range_check CHECK (to_time > from_time)
);
CREATE INDEX idx_analysis_runs_session
    ON analysis_runs (session_id, created_at);
CREATE INDEX idx_analysis_runs_status ON analysis_runs (status);

CREATE TABLE aoi_hits (
    run_id         UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    sample_id      BIGINT NOT NULL,
    event_time     TIMESTAMPTZ NOT NULL,
    definition_id  UUID NOT NULL REFERENCES aoi_definitions(id) ON DELETE CASCADE,
    PRIMARY KEY (run_id, sample_id, event_time, definition_id),
    FOREIGN KEY (sample_id, event_time)
        REFERENCES gaze_samples(id, event_time) ON DELETE CASCADE
);
CREATE INDEX idx_aoi_hits_run ON aoi_hits (run_id);
CREATE INDEX idx_aoi_hits_definition ON aoi_hits (definition_id);

CREATE TABLE presentation_metrics (
    presentation_id    UUID NOT NULL REFERENCES content_presentations(id) ON DELETE CASCADE,
    algorithm_version  VARCHAR(64) NOT NULL,
    batch_watermark    UUID REFERENCES gaze_batches(id) ON DELETE SET NULL,
    sample_count       INTEGER NOT NULL DEFAULT 0
                       CONSTRAINT presentation_metrics_sample_count_check
                       CHECK (sample_count >= 0),
    on_slide_count     INTEGER NOT NULL DEFAULT 0
                       CONSTRAINT presentation_metrics_on_slide_count_check
                       CHECK (on_slide_count >= 0),
    dwell_ms           BIGINT NOT NULL DEFAULT 0
                       CONSTRAINT presentation_metrics_dwell_ms_check
                       CHECK (dwell_ms >= 0),
    fixation_count     INTEGER NOT NULL DEFAULT 0
                       CONSTRAINT presentation_metrics_fixation_count_check
                       CHECK (fixation_count >= 0),
    heatmap_grid       JSONB NOT NULL DEFAULT '[]'::jsonb,
    computed_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (presentation_id, algorithm_version)
);

-- ---------------------------------------------------------------------------
-- 11) Chat
-- ---------------------------------------------------------------------------
CREATE TABLE chat_sessions (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id          UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    course_version_id  UUID REFERENCES course_versions(id) ON DELETE SET NULL,
    lesson_id          UUID REFERENCES lessons(id) ON DELETE SET NULL,
    lesson_version_id  UUID REFERENCES lesson_versions(id) ON DELETE SET NULL,
    quiz_attempt_id    UUID REFERENCES quiz_attempts(id) ON DELETE SET NULL,
    title              VARCHAR(255) NOT NULL DEFAULT 'Phiên mới',
    context_key        TEXT NOT NULL DEFAULT '',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at        TIMESTAMPTZ
);
CREATE INDEX idx_chat_sessions_student_course
    ON chat_sessions (student_id, course_id, updated_at);

CREATE TABLE chat_messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role        VARCHAR(10) NOT NULL
                CONSTRAINT chat_messages_role_check
                CHECK (role IN ('student', 'assistant')),
    content     TEXT NOT NULL,
    citations   JSONB NOT NULL DEFAULT '[]'::jsonb
                CONSTRAINT chat_messages_citations_array_check
                CHECK (jsonb_typeof(citations) = 'array'),
    intent      VARCHAR(30),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_chat_messages_session
    ON chat_messages (session_id, created_at);

-- ---------------------------------------------------------------------------
-- 12) Metadata / migration tracking
-- ---------------------------------------------------------------------------
CREATE TABLE app_metadata (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- schema_migrations do runner tạo trước baseline (xem db/migrate.sh).

-- ---------------------------------------------------------------------------
-- 13) Circular FKs (deferrable)
-- ---------------------------------------------------------------------------
ALTER TABLE courses
    ADD CONSTRAINT courses_published_version_fkey
    FOREIGN KEY (published_version_id) REFERENCES course_versions(id)
    ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE devices
    ADD CONSTRAINT devices_current_calibration_fkey
    FOREIGN KEY (current_calibration_id) REFERENCES calibrations(id)
    ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE aoi_layout_snapshots
    ADD CONSTRAINT aoi_layout_snapshots_ui_set_fkey
    FOREIGN KEY (ui_aoi_set_id) REFERENCES aoi_sets(id)
    ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;

-- ---------------------------------------------------------------------------
-- 14) Views
-- ---------------------------------------------------------------------------
CREATE VIEW v_published_course_outline AS
SELECT
    c.id                    AS course_id,
    cv.id                   AS course_version_id,
    cv.version_no           AS course_version_no,
    cvm.id                  AS module_id,
    cvm.module_key          AS module_key,
    cvm.title               AS module_title,
    cvm.position            AS module_position,
    cvi.id                  AS item_id,
    cvi.position            AS item_position,
    l.id                    AS lesson_id,
    l.kind                  AS lesson_kind,
    lv.id                   AS lesson_version_id,
    lv.title                AS lesson_title,
    lvs.id                  AS lesson_version_slide_id,
    lvs.position            AS slide_position,
    lvs.title               AS slide_title,
    lvs.is_key              AS is_key,
    sv.id                   AS slide_version_id,
    s.id                    AS slide_id,
    sv.revision_no          AS slide_revision_no,
    sv.image_asset_id       AS image_asset_id,
    ma.object_key           AS image_object_key,
    ma.storage_backend      AS image_storage_backend,
    ma.mime_type            AS image_mime_type,
    sv.source_pdf_asset_id  AS source_pdf_asset_id,
    sv.source_page          AS source_page
FROM courses c
JOIN course_versions cv
  ON cv.id = c.published_version_id AND cv.state = 'published'
JOIN course_version_modules cvm
  ON cvm.course_version_id = cv.id
JOIN course_version_items cvi
  ON cvi.module_id = cvm.id
JOIN lessons l
  ON l.id = cvi.lesson_id
JOIN lesson_versions lv
  ON lv.id = cvi.lesson_version_id AND lv.state = 'published'
LEFT JOIN lesson_version_slides lvs
  ON lvs.lesson_version_id = lv.id
LEFT JOIN slide_versions sv
  ON sv.id = lvs.slide_version_id
LEFT JOIN slides s
  ON s.id = lvs.slide_id
LEFT JOIN media_assets ma
  ON ma.id = sv.image_asset_id
WHERE c.archived_at IS NULL;

CREATE VIEW v_chatbot_slide_documents AS
SELECT
    sd.slide_version_id,
    o.course_id,
    o.course_version_id,
    o.lesson_id,
    o.lesson_version_id,
    o.lesson_version_slide_id,
    o.slide_id,
    o.image_asset_id,
    o.image_object_key,
    o.image_storage_backend,
    o.image_mime_type,
    o.slide_title,
    o.module_title,
    o.lesson_title,
    o.slide_position,
    sd.transcript,
    sd.embedding,
    sd.content_tsv,
    sd.pipeline_version,
    sd.model_version,
    sd.ingestion_state
FROM slide_documents sd
JOIN v_published_course_outline o
  ON o.slide_version_id = sd.slide_version_id
WHERE sd.ingestion_state = 'ready';

CREATE VIEW v_session_metrics AS
SELECT
    ls.id                     AS session_id,
    ls.enrollment_id          AS enrollment_id,
    ls.course_version_item_id AS course_version_item_id,
    cvi.lesson_id             AS lesson_id,
    cvi.lesson_version_id     AS lesson_version_id,
    (SELECT count(*) FROM gaze_samples gs WHERE gs.session_id = ls.id) AS sample_count,
    (SELECT count(*) FROM gaze_samples gs
      WHERE gs.session_id = ls.id AND gs.status = 'ok') AS ok_sample_count,
    (SELECT coalesce(sum(pm.dwell_ms), 0)
       FROM content_presentations cp
       JOIN presentation_metrics pm ON pm.presentation_id = cp.id
      WHERE cp.session_id = ls.id) AS dwell_ms,
    (SELECT coalesce(sum(pm.fixation_count), 0)
       FROM content_presentations cp
       JOIN presentation_metrics pm ON pm.presentation_id = cp.id
      WHERE cp.session_id = ls.id) AS fixation_count
FROM learning_sessions ls
JOIN course_version_items cvi ON cvi.id = ls.course_version_item_id;

CREATE VIEW v_lesson_version_metrics AS
SELECT
    ls.enrollment_id          AS enrollment_id,
    cvi.lesson_version_id     AS lesson_version_id,
    cvi.lesson_id             AS lesson_id,
    count(DISTINCT lvs.id)    AS slides_total,
    count(DISTINCT lvs.id) FILTER (WHERE pm.dwell_ms > 0) AS slides_viewed,
    coalesce(sum(pm.dwell_ms), 0) AS dwell_ms,
    coalesce(avg(CASE WHEN lvs.is_key THEN pm.dwell_ms END), 0) AS key_dwell_ms,
    coalesce(avg(CASE WHEN NOT lvs.is_key THEN pm.dwell_ms END), 0) AS normal_dwell_ms
FROM learning_sessions ls
JOIN course_version_items cvi ON cvi.id = ls.course_version_item_id
JOIN lesson_version_slides lvs ON lvs.lesson_version_id = cvi.lesson_version_id
LEFT JOIN content_presentations cp
  ON cp.session_id = ls.id AND cp.lesson_version_slide_id = lvs.id
LEFT JOIN presentation_metrics pm ON pm.presentation_id = cp.id
GROUP BY ls.enrollment_id, cvi.lesson_version_id, cvi.lesson_id;

CREATE VIEW v_class_heatmap AS
SELECT
    cvi.lesson_version_id     AS lesson_version_id,
    lvs.slide_version_id      AS slide_version_id,
    pm.algorithm_version      AS algorithm_version,
    jsonb_agg(pm.heatmap_grid) AS heatmap_grids,
    sum(pm.sample_count)      AS sample_count,
    sum(pm.dwell_ms)          AS dwell_ms
FROM presentation_metrics pm
JOIN content_presentations cp ON cp.id = pm.presentation_id
JOIN learning_sessions ls ON ls.id = cp.session_id
JOIN course_version_items cvi ON cvi.id = ls.course_version_item_id
JOIN lesson_version_slides lvs ON lvs.id = cp.lesson_version_slide_id
GROUP BY cvi.lesson_version_id, lvs.slide_version_id, pm.algorithm_version;

-- ---------------------------------------------------------------------------
-- 15) Immutability / consistency triggers
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION prevent_published_course_version_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.state = 'published' THEN
            RAISE EXCEPTION 'cannot delete published course version %', OLD.id;
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.state = 'published' THEN
        IF NEW.state = 'archived'
           AND NEW.title = OLD.title
           AND NEW.description IS NOT DISTINCT FROM OLD.description
           AND NEW.thumbnail_asset_id IS NOT DISTINCT FROM OLD.thumbnail_asset_id
           AND NEW.generation = OLD.generation THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'cannot modify published course version %', OLD.id;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_course_versions_immutable
BEFORE UPDATE OR DELETE ON course_versions
FOR EACH ROW EXECUTE FUNCTION prevent_published_course_version_mutation();

CREATE OR REPLACE FUNCTION prevent_published_lesson_version_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.state = 'published' THEN
            RAISE EXCEPTION 'cannot delete published lesson version %', OLD.id;
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.state = 'published' THEN
        IF NEW.state = 'archived'
           AND NEW.title = OLD.title THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'cannot modify published lesson version %', OLD.id;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_lesson_versions_immutable
BEFORE UPDATE OR DELETE ON lesson_versions
FOR EACH ROW EXECUTE FUNCTION prevent_published_lesson_version_mutation();

CREATE OR REPLACE FUNCTION prevent_slide_version_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'slide_versions are immutable';
END;
$$;
CREATE TRIGGER trg_slide_versions_immutable
BEFORE UPDATE OR DELETE ON slide_versions
FOR EACH ROW EXECUTE FUNCTION prevent_slide_version_mutation();

CREATE OR REPLACE FUNCTION prevent_media_asset_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.state <> 'deleted' THEN
            RAISE EXCEPTION 'media asset % must be marked deleted before removal', OLD.id;
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.state = 'ready' THEN
        IF NEW.object_key <> OLD.object_key
           OR NEW.sha256 <> OLD.sha256
           OR NEW.mime_type <> OLD.mime_type
           OR NEW.byte_size <> OLD.byte_size
           OR NEW.image_width IS DISTINCT FROM OLD.image_width
           OR NEW.image_height IS DISTINCT FROM OLD.image_height THEN
            RAISE EXCEPTION 'ready media asset % is immutable', OLD.id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_media_assets_immutable
BEFORE UPDATE OR DELETE ON media_assets
FOR EACH ROW EXECUTE FUNCTION prevent_media_asset_mutation();

CREATE OR REPLACE FUNCTION prevent_calibration_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'calibrations are immutable';
END;
$$;
CREATE TRIGGER trg_calibrations_immutable
BEFORE UPDATE OR DELETE ON calibrations
FOR EACH ROW EXECUTE FUNCTION prevent_calibration_mutation();

CREATE OR REPLACE FUNCTION prevent_submitted_attempt_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.status = 'submitted' THEN
            RAISE EXCEPTION 'cannot delete submitted attempt %', OLD.id;
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.status = 'submitted' THEN
        RAISE EXCEPTION 'cannot modify submitted attempt %', OLD.id;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_quiz_attempts_submitted_immutable
BEFORE UPDATE OR DELETE ON quiz_attempts
FOR EACH ROW EXECUTE FUNCTION prevent_submitted_attempt_mutation();

CREATE OR REPLACE FUNCTION check_course_version_item_consistency()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    course_id UUID;
    lesson_course_id UUID;
BEGIN
    SELECT cv.course_id INTO course_id
      FROM course_versions cv WHERE cv.id = NEW.course_version_id;
    SELECT l.course_id INTO lesson_course_id
      FROM lessons l WHERE l.id = NEW.lesson_id;
    IF course_id IS NULL OR lesson_course_id IS NULL OR course_id <> lesson_course_id THEN
        RAISE EXCEPTION 'course_version_item lesson % does not belong to course version %',
            NEW.lesson_id, NEW.course_version_id;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_course_version_item_consistency
BEFORE INSERT OR UPDATE ON course_version_items
FOR EACH ROW EXECUTE FUNCTION check_course_version_item_consistency();

CREATE OR REPLACE FUNCTION check_lesson_version_slide_consistency()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    lesson_id UUID;
    slide_lesson_id UUID;
BEGIN
    SELECT lv.lesson_id INTO lesson_id
      FROM lesson_versions lv WHERE lv.id = NEW.lesson_version_id;
    SELECT s.lesson_id INTO slide_lesson_id
      FROM slides s WHERE s.id = NEW.slide_id;
    IF lesson_id IS NULL OR slide_lesson_id IS NULL OR lesson_id <> slide_lesson_id THEN
        RAISE EXCEPTION 'slide % does not belong to lesson version %',
            NEW.slide_id, NEW.lesson_version_id;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_lesson_version_slide_consistency
BEFORE INSERT OR UPDATE ON lesson_version_slides
FOR EACH ROW EXECUTE FUNCTION check_lesson_version_slide_consistency();

CREATE OR REPLACE FUNCTION check_quiz_attempt_consistency()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    enrollment_course UUID;
    item_course UUID;
    item_lesson UUID;
BEGIN
    SELECT e.course_id INTO enrollment_course
      FROM enrollments e WHERE e.id = NEW.enrollment_id;
    SELECT cv.course_id, cvi.lesson_id INTO item_course, item_lesson
      FROM course_version_items cvi
      JOIN course_versions cv ON cv.id = cvi.course_version_id
     WHERE cvi.id = NEW.course_version_item_id;
    IF enrollment_course IS NULL OR item_course IS NULL OR enrollment_course <> item_course THEN
        RAISE EXCEPTION 'quiz attempt enrollment % does not match item course',
            NEW.enrollment_id;
    END IF;
    IF item_lesson <> NEW.lesson_id THEN
        RAISE EXCEPTION 'quiz attempt lesson % does not match item lesson %',
            NEW.lesson_id, item_lesson;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_quiz_attempt_consistency
BEFORE INSERT OR UPDATE ON quiz_attempts
FOR EACH ROW EXECUTE FUNCTION check_quiz_attempt_consistency();

CREATE OR REPLACE FUNCTION check_learning_session_consistency()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    enrollment_course UUID;
    enrollment_student UUID;
    item_course UUID;
    attempt_enrollment UUID;
    attempt_item UUID;
    calibration_owner UUID;
BEGIN
    SELECT e.course_id, e.student_id INTO enrollment_course, enrollment_student
      FROM enrollments e WHERE e.id = NEW.enrollment_id;
    SELECT cv.course_id INTO item_course
      FROM course_version_items cvi
      JOIN course_versions cv ON cv.id = cvi.course_version_id
     WHERE cvi.id = NEW.course_version_item_id;
    IF enrollment_course IS NULL OR item_course IS NULL OR enrollment_course <> item_course THEN
        RAISE EXCEPTION 'learning session enrollment % does not match item course',
            NEW.enrollment_id;
    END IF;
    IF NEW.quiz_attempt_id IS NOT NULL THEN
        SELECT qa.enrollment_id, qa.course_version_item_id
          INTO attempt_enrollment, attempt_item
          FROM quiz_attempts qa WHERE qa.id = NEW.quiz_attempt_id;
        IF attempt_enrollment <> NEW.enrollment_id OR attempt_item <> NEW.course_version_item_id THEN
            RAISE EXCEPTION 'learning session attempt % does not match enrollment/item',
                NEW.quiz_attempt_id;
        END IF;
    END IF;
    IF NEW.calibration_id IS NOT NULL THEN
        SELECT d.owner_id INTO calibration_owner
          FROM calibrations c
          JOIN devices d ON d.id = c.device_id
         WHERE c.id = NEW.calibration_id;
        IF calibration_owner <> enrollment_student THEN
            RAISE EXCEPTION 'learning session calibration % does not belong to student',
                NEW.calibration_id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_learning_session_consistency
BEFORE INSERT OR UPDATE ON learning_sessions
FOR EACH ROW EXECUTE FUNCTION check_learning_session_consistency();

CREATE OR REPLACE FUNCTION check_presentation_consistency()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    session_lesson_version UUID;
    slide_lesson_version UUID;
BEGIN
    SELECT cvi.lesson_version_id INTO session_lesson_version
      FROM learning_sessions ls
      JOIN course_version_items cvi ON cvi.id = ls.course_version_item_id
     WHERE ls.id = NEW.session_id;
    IF NEW.lesson_version_slide_id IS NOT NULL THEN
        SELECT lvs.lesson_version_id INTO slide_lesson_version
          FROM lesson_version_slides lvs
         WHERE lvs.id = NEW.lesson_version_slide_id;
        IF slide_lesson_version <> session_lesson_version THEN
            RAISE EXCEPTION 'presentation slide % does not belong to session lesson version',
                NEW.lesson_version_slide_id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_presentation_consistency
BEFORE INSERT OR UPDATE ON content_presentations
FOR EACH ROW EXECUTE FUNCTION check_presentation_consistency();

CREATE OR REPLACE FUNCTION check_gaze_batch_consistency()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    presentation_session UUID;
    snapshot_presentation UUID;
BEGIN
    SELECT cp.session_id INTO presentation_session
      FROM content_presentations cp WHERE cp.id = NEW.presentation_id;
    IF presentation_session <> NEW.session_id THEN
        RAISE EXCEPTION 'gaze batch presentation % does not belong to session %',
            NEW.presentation_id, NEW.session_id;
    END IF;
    IF NEW.layout_snapshot_id IS NOT NULL THEN
        SELECT als.presentation_id INTO snapshot_presentation
          FROM aoi_layout_snapshots als WHERE als.id = NEW.layout_snapshot_id;
        IF snapshot_presentation <> NEW.presentation_id THEN
            RAISE EXCEPTION 'gaze batch layout % does not belong to presentation %',
                NEW.layout_snapshot_id, NEW.presentation_id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_gaze_batch_consistency
BEFORE INSERT OR UPDATE ON gaze_batches
FOR EACH ROW EXECUTE FUNCTION check_gaze_batch_consistency();

CREATE OR REPLACE FUNCTION check_gaze_sample_batch_range()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    b_start BIGINT;
    b_end BIGINT;
BEGIN
    SELECT sequence_start, sequence_end INTO b_start, b_end
      FROM gaze_batches WHERE id = NEW.batch_id;
    IF NEW.sequence < b_start OR NEW.sequence > b_end THEN
        RAISE EXCEPTION 'gaze sample sequence % outside batch range [%, %]',
            NEW.sequence, b_start, b_end;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_gaze_sample_batch_range
BEFORE INSERT ON gaze_samples
FOR EACH ROW EXECUTE FUNCTION check_gaze_sample_batch_range();

CREATE OR REPLACE FUNCTION check_aoi_definition_parent()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent_set UUID;
BEGIN
    IF NEW.parent_id IS NOT NULL THEN
        SELECT aoi_set_id INTO parent_set
          FROM aoi_definitions WHERE id = NEW.parent_id;
        IF parent_set <> NEW.aoi_set_id THEN
            RAISE EXCEPTION 'AOI parent % does not belong to set %',
                NEW.parent_id, NEW.aoi_set_id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_aoi_definition_parent
BEFORE INSERT OR UPDATE ON aoi_definitions
FOR EACH ROW EXECUTE FUNCTION check_aoi_definition_parent();

CREATE OR REPLACE FUNCTION check_aoi_hit_consistency()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    run_set UUID;
    definition_set UUID;
    sample_session UUID;
    run_session UUID;
BEGIN
    SELECT aoi_set_id, session_id INTO run_set, run_session
      FROM analysis_runs WHERE id = NEW.run_id;
    SELECT aoi_set_id INTO definition_set
      FROM aoi_definitions WHERE id = NEW.definition_id;
    IF run_set <> definition_set THEN
        RAISE EXCEPTION 'AOI hit definition % does not belong to run set %',
            NEW.definition_id, run_set;
    END IF;
    SELECT session_id INTO sample_session
      FROM gaze_samples WHERE id = NEW.sample_id AND event_time = NEW.event_time;
    IF sample_session <> run_session THEN
        RAISE EXCEPTION 'AOI hit sample % does not belong to run session', NEW.sample_id;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_aoi_hit_consistency
BEFORE INSERT OR UPDATE ON aoi_hits
FOR EACH ROW EXECUTE FUNCTION check_aoi_hit_consistency();

CREATE OR REPLACE FUNCTION check_course_published_pointer()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    version_course UUID;
    version_state VARCHAR(16);
BEGIN
    IF NEW.published_version_id IS NOT NULL THEN
        SELECT course_id, state INTO version_course, version_state
          FROM course_versions WHERE id = NEW.published_version_id;
        IF version_course <> NEW.id OR version_state <> 'published' THEN
            RAISE EXCEPTION 'published_version_id % must be a published version of course %',
                NEW.published_version_id, NEW.id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_course_published_pointer
BEFORE INSERT OR UPDATE OF published_version_id ON courses
FOR EACH ROW EXECUTE FUNCTION check_course_published_pointer();

CREATE OR REPLACE FUNCTION check_device_current_calibration()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    calibration_device UUID;
BEGIN
    IF NEW.current_calibration_id IS NOT NULL THEN
        SELECT device_id INTO calibration_device
          FROM calibrations WHERE id = NEW.current_calibration_id;
        IF calibration_device <> NEW.id THEN
            RAISE EXCEPTION 'current_calibration_id % does not belong to device %',
                NEW.current_calibration_id, NEW.id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_device_current_calibration
BEFORE INSERT OR UPDATE OF current_calibration_id ON devices
FOR EACH ROW EXECUTE FUNCTION check_device_current_calibration();

CREATE OR REPLACE FUNCTION check_chat_session_context()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    course_version_course UUID;
    lesson_course UUID;
    lesson_version_lesson UUID;
    attempt_enrollment UUID;
    attempt_lesson UUID;
    attempt_course UUID;
BEGIN
    IF NEW.course_version_id IS NOT NULL THEN
        SELECT course_id INTO course_version_course
          FROM course_versions WHERE id = NEW.course_version_id;
        IF course_version_course <> NEW.course_id THEN
            RAISE EXCEPTION 'chat session course version % does not belong to course %',
                NEW.course_version_id, NEW.course_id;
        END IF;
    END IF;
    IF NEW.lesson_id IS NOT NULL THEN
        SELECT course_id INTO lesson_course
          FROM lessons WHERE id = NEW.lesson_id;
        IF lesson_course <> NEW.course_id THEN
            RAISE EXCEPTION 'chat session lesson % does not belong to course %',
                NEW.lesson_id, NEW.course_id;
        END IF;
    END IF;
    IF NEW.lesson_version_id IS NOT NULL THEN
        SELECT lesson_id INTO lesson_version_lesson
          FROM lesson_versions WHERE id = NEW.lesson_version_id;
        IF lesson_version_lesson <> NEW.lesson_id THEN
            RAISE EXCEPTION 'chat session lesson version % does not belong to lesson %',
                NEW.lesson_version_id, NEW.lesson_id;
        END IF;
    END IF;
    IF NEW.quiz_attempt_id IS NOT NULL THEN
        SELECT qa.enrollment_id, qa.lesson_id INTO attempt_enrollment, attempt_lesson
          FROM quiz_attempts qa WHERE qa.id = NEW.quiz_attempt_id;
        SELECT e.course_id INTO attempt_course
          FROM enrollments e WHERE e.id = attempt_enrollment;
        IF attempt_course <> NEW.course_id OR attempt_lesson <> NEW.lesson_id THEN
            RAISE EXCEPTION 'chat session attempt % does not match course/lesson',
                NEW.quiz_attempt_id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_chat_session_context
BEFORE INSERT OR UPDATE ON chat_sessions
FOR EACH ROW EXECUTE FUNCTION check_chat_session_context();

CREATE OR REPLACE FUNCTION check_analysis_run_scope()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    session_lesson_version UUID;
    set_scope VARCHAR(16);
    set_slide_version UUID;
    slide_lesson_version UUID;
BEGIN
    SELECT cvi.lesson_version_id INTO session_lesson_version
      FROM learning_sessions ls
      JOIN course_version_items cvi ON cvi.id = ls.course_version_item_id
     WHERE ls.id = NEW.session_id;
    SELECT scope, slide_version_id INTO set_scope, set_slide_version
      FROM aoi_sets WHERE id = NEW.aoi_set_id;
    IF set_scope = 'slide' THEN
        SELECT lvs.lesson_version_id INTO slide_lesson_version
          FROM lesson_version_slides lvs
         WHERE lvs.slide_version_id = set_slide_version
         LIMIT 1;
        IF slide_lesson_version <> session_lesson_version THEN
            RAISE EXCEPTION 'analysis run AOI set % does not belong to session lesson version',
                NEW.aoi_set_id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_analysis_run_scope
BEFORE INSERT OR UPDATE ON analysis_runs
FOR EACH ROW EXECUTE FUNCTION check_analysis_run_scope();

CREATE OR REPLACE FUNCTION prevent_published_aoi_set_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.state = 'published' THEN
            RAISE EXCEPTION 'cannot delete published AOI set %', OLD.id;
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.state = 'published' THEN
        IF NEW.state = 'archived'
           AND NEW.scope = OLD.scope
           AND NEW.slide_version_id IS NOT DISTINCT FROM OLD.slide_version_id
           AND NEW.ui_schema_version IS NOT DISTINCT FROM OLD.ui_schema_version
           AND NEW.revision = OLD.revision THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'cannot modify published AOI set %', OLD.id;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_aoi_sets_immutable
BEFORE UPDATE OR DELETE ON aoi_sets
FOR EACH ROW EXECUTE FUNCTION prevent_published_aoi_set_mutation();

CREATE OR REPLACE FUNCTION prevent_published_aoi_definition_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    old_state VARCHAR(16);
    new_state VARCHAR(16);
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        SELECT state INTO old_state FROM aoi_sets WHERE id = OLD.aoi_set_id;
        IF old_state <> 'draft' THEN
            RAISE EXCEPTION 'cannot modify definitions of non-draft AOI set %', OLD.aoi_set_id;
        END IF;
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        SELECT state INTO new_state FROM aoi_sets WHERE id = NEW.aoi_set_id;
        IF new_state <> 'draft' THEN
            RAISE EXCEPTION 'cannot add definitions to non-draft AOI set %', NEW.aoi_set_id;
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_aoi_definitions_immutable
BEFORE INSERT OR UPDATE OR DELETE ON aoi_definitions
FOR EACH ROW EXECUTE FUNCTION prevent_published_aoi_definition_mutation();

CREATE OR REPLACE FUNCTION check_quiz_spec_lesson_kind()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    lesson_kind VARCHAR(10);
BEGIN
    SELECT l.kind INTO lesson_kind
      FROM lesson_versions lv
      JOIN lessons l ON l.id = lv.lesson_id
     WHERE lv.id = NEW.lesson_version_id;
    IF lesson_kind <> 'quiz' THEN
        RAISE EXCEPTION 'quiz_specs lesson version % is not a quiz',
            NEW.lesson_version_id;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_quiz_spec_lesson_kind
BEFORE INSERT OR UPDATE ON quiz_specs
FOR EACH ROW EXECUTE FUNCTION check_quiz_spec_lesson_kind();
