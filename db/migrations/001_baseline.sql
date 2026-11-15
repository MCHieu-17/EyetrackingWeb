-- =============================================================================
-- 001_baseline.sql — schema generation 12 của EyeLearning.
--
-- Schema tinh gọn: 24 bảng lõi, không versioning nội dung.
-- Xóa khóa học/chương/bài/slide sẽ cascade toàn bộ dữ liệu học tập liên quan.
-- Chạy từ database rỗng; runner bọc file trong một transaction.
--
-- Generation 12 gộp luôn các thay đổi của generation 11:
--   * course_visits + learning_sessions.course_visit_id.
--   * gaze_samples.original_viewport_x/y.
--   * view_layouts.coordinate_space/visible_rect.
-- Đồng thời thêm nhãn phân tích AOI:
--   * aois.label cho leaf slide (AOI_1, AOI_2, ...).
--   * gaze_samples.aoi_label: một nhãn duy nhất mỗi sample.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS unaccent;

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
-- 1) Danh tính & phân quyền (5 bảng)
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL,
    password_hash   VARCHAR(255),
    role            VARCHAR(16) NOT NULL DEFAULT 'student'
                    CONSTRAINT users_role_check
                    CHECK (role IN ('admin', 'teacher', 'student')),
    status          VARCHAR(20) NOT NULL DEFAULT 'active'
                    CONSTRAINT users_status_check
                    CHECK (status IN ('active', 'suspended', 'banned')),
    full_name       VARCHAR(150) NOT NULL DEFAULT '',
    date_of_birth   DATE,
    gender          VARCHAR(20)
                    CONSTRAINT users_gender_check
                    CHECK (gender IN ('male', 'female', 'other')),
    phone           VARCHAR(20),
    avatar_url      TEXT,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);
CREATE UNIQUE INDEX ux_users_email_lower ON users (lower(email));
CREATE INDEX idx_users_role ON users (role);

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

CREATE TABLE oauth_accounts (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider          VARCHAR(30) NOT NULL,
    provider_user_id  VARCHAR(255) NOT NULL,
    email             VARCHAR(255),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at     TIMESTAMPTZ,
    CONSTRAINT oauth_accounts_provider_user_unique
        UNIQUE (provider, provider_user_id)
);
CREATE INDEX idx_oauth_accounts_user ON oauth_accounts (user_id);

CREATE TABLE student_profiles (
    user_id       UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    student_code  VARCHAR(30) NOT NULL UNIQUE,
    program       VARCHAR(200)
);

CREATE TABLE teacher_profiles (
    user_id       UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    teacher_code  VARCHAR(30) NOT NULL UNIQUE,
    department    VARCHAR(150)
);

-- ---------------------------------------------------------------------------
-- 2) Khóa học, ghi danh, media (4 bảng)
-- ---------------------------------------------------------------------------
CREATE TABLE courses (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id              UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_by            UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    title                 VARCHAR(255) NOT NULL,
    description           TEXT,
    thumbnail_url         TEXT,
    status                VARCHAR(16) NOT NULL DEFAULT 'draft'
                          CONSTRAINT courses_status_check
                          CHECK (status IN ('draft', 'published', 'archived')),
    published_at          TIMESTAMPTZ,
    show_gaze_dot         BOOLEAN NOT NULL DEFAULT false,
    require_calibration   BOOLEAN NOT NULL DEFAULT true,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_courses_owner ON courses (owner_id);
CREATE INDEX idx_courses_status ON courses (status);

CREATE TABLE course_teachers (
    course_id    UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    teacher_id   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
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

-- "Ca học" cấp khóa: mỗi lần sinh viên vào trang khóa là một ca.
CREATE TABLE course_visits (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enrollment_id  UUID NOT NULL REFERENCES enrollments(id) ON DELETE CASCADE,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at       TIMESTAMPTZ,
    last_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    status         VARCHAR(16) NOT NULL DEFAULT 'active'
                   CONSTRAINT course_visits_status_check
                   CHECK (status IN ('active', 'ended', 'expired')),
    visit_key      TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_course_visits_enrollment_key
    ON course_visits (enrollment_id, visit_key)
    WHERE visit_key IS NOT NULL;
CREATE INDEX idx_course_visits_enrollment
    ON course_visits (enrollment_id, started_at);
CREATE INDEX idx_course_visits_status_seen
    ON course_visits (status, last_seen_at);

CREATE TABLE media_assets (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id         UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
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
    state             VARCHAR(16) NOT NULL DEFAULT 'staging'
                      CONSTRAINT media_assets_state_check
                      CHECK (state IN ('staging', 'ready', 'failed', 'deleted')),
    page_count        INTEGER
                      CONSTRAINT media_assets_page_count_check
                      CHECK (page_count IS NULL OR page_count > 0),
    source_format     VARCHAR(16),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (course_id, sha256),
    UNIQUE (storage_backend, object_key)
);
CREATE INDEX idx_media_assets_course ON media_assets (course_id);

-- ---------------------------------------------------------------------------
-- 3) Nội dung hiện hành (3 bảng)
-- ---------------------------------------------------------------------------
CREATE TABLE course_modules (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id   UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title       VARCHAR(255) NOT NULL,
    position    INTEGER NOT NULL
                CONSTRAINT course_modules_position_check CHECK (position >= 0),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (course_id, position)
);
CREATE INDEX idx_course_modules_course ON course_modules (course_id);

CREATE TABLE lessons (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id     UUID NOT NULL REFERENCES course_modules(id) ON DELETE CASCADE,
    title         VARCHAR(255) NOT NULL,
    kind          VARCHAR(10) NOT NULL
                  CONSTRAINT lessons_kind_check
                  CHECK (kind IN ('lesson', 'quiz')),
    position      INTEGER NOT NULL
                  CONSTRAINT lessons_position_check CHECK (position >= 0),
    pdf_asset_id  UUID REFERENCES media_assets(id) ON DELETE SET NULL,
    quiz_config   JSONB NOT NULL DEFAULT '{}'::jsonb
                  CONSTRAINT lessons_quiz_config_check
                  CHECK (jsonb_typeof(quiz_config) = 'object'),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (module_id, position)
);
CREATE INDEX idx_lessons_module ON lessons (module_id);
CREATE INDEX idx_lessons_kind ON lessons (kind);

CREATE TABLE slides (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_id             UUID NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    position              INTEGER NOT NULL
                          CONSTRAINT slides_position_check CHECK (position >= 0),
    page_number           INTEGER NOT NULL
                          CONSTRAINT slides_page_number_check CHECK (page_number > 0),
    title                 VARCHAR(255) NOT NULL DEFAULT '',
    aoi_suggestions       JSONB NOT NULL DEFAULT '[]'::jsonb
                          CONSTRAINT slides_aoi_suggestions_check
                          CHECK (jsonb_typeof(aoi_suggestions) = 'array'),
    transcript            TEXT NOT NULL DEFAULT '',
    embedding             VECTOR(1024),
    content_tsv           TSVECTOR GENERATED ALWAYS AS (
                              to_tsvector('simple', immutable_unaccent(transcript))
                          ) STORED,
    index_status          VARCHAR(16) NOT NULL DEFAULT 'none'
                          CONSTRAINT slides_index_status_check
                          CHECK (index_status IN ('none', 'pending', 'ready', 'failed')),
    index_error           TEXT,
    pipeline_version      VARCHAR(64) NOT NULL DEFAULT 'v1',
    model_version         VARCHAR(64) NOT NULL DEFAULT 'v1',
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (lesson_id, position)
);
CREATE INDEX idx_slides_lesson ON slides (lesson_id);
CREATE INDEX idx_slides_index_status ON slides (index_status);
CREATE INDEX idx_slides_tsv ON slides USING gin (content_tsv);
CREATE INDEX idx_slides_hnsw ON slides
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ---------------------------------------------------------------------------
-- 4) Hàng đợi nền dùng chung (1 bảng)
-- ---------------------------------------------------------------------------
CREATE TABLE background_jobs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_id      UUID NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    kind           VARCHAR(24) NOT NULL
                   CONSTRAINT background_jobs_kind_check
                   CHECK (kind IN ('import_slides', 'index_slides', 'analyze_lesson')),
    status         VARCHAR(16) NOT NULL DEFAULT 'queued'
                   CONSTRAINT background_jobs_status_check
                   CHECK (status IN ('queued', 'processing', 'ready', 'failed', 'cancelled')),
    payload        JSONB NOT NULL DEFAULT '{}'::jsonb
                   CONSTRAINT background_jobs_payload_check
                   CHECK (jsonb_typeof(payload) = 'object'),
    attempts       INTEGER NOT NULL DEFAULT 0
                   CONSTRAINT background_jobs_attempts_check CHECK (attempts >= 0),
    max_attempts   INTEGER NOT NULL DEFAULT 3
                   CONSTRAINT background_jobs_max_attempts_check CHECK (max_attempts > 0),
    error          TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at     TIMESTAMPTZ,
    finished_at    TIMESTAMPTZ,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_background_jobs_claim
    ON background_jobs (kind, status, created_at);
CREATE INDEX idx_background_jobs_lesson
    ON background_jobs (lesson_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- 5) Quiz (1 bảng)
-- ---------------------------------------------------------------------------
CREATE TABLE quiz_attempts (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enrollment_id          UUID NOT NULL REFERENCES enrollments(id) ON DELETE CASCADE,
    lesson_id              UUID NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    attempt_no             INTEGER NOT NULL
                           CONSTRAINT quiz_attempts_attempt_no_check CHECK (attempt_no > 0),
    status                 VARCHAR(16) NOT NULL DEFAULT 'in_progress'
                           CONSTRAINT quiz_attempts_status_check
                           CHECK (status IN ('in_progress', 'submitted', 'expired')),
    started_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at             TIMESTAMPTZ NOT NULL,
    submitted_at           TIMESTAMPTZ,
    quiz_snapshot          JSONB NOT NULL DEFAULT '{}'::jsonb
                           CONSTRAINT quiz_attempts_snapshot_object_check
                           CHECK (jsonb_typeof(quiz_snapshot) = 'object'),
    answers                JSONB NOT NULL DEFAULT '{}'::jsonb
                           CONSTRAINT quiz_attempts_answers_object_check
                           CHECK (jsonb_typeof(answers) = 'object'),
    grading                JSONB NOT NULL DEFAULT '{}'::jsonb
                           CONSTRAINT quiz_attempts_grading_object_check
                           CHECK (jsonb_typeof(grading) = 'object'),
    score                  REAL
                           CONSTRAINT quiz_attempts_score_check
                           CHECK (score IS NULL OR score >= 0),
    max_score              REAL
                           CONSTRAINT quiz_attempts_max_score_check
                           CHECK (max_score IS NULL OR max_score >= 0),
    UNIQUE (enrollment_id, lesson_id, attempt_no)
);
CREATE UNIQUE INDEX ux_quiz_attempts_one_in_progress
    ON quiz_attempts (enrollment_id, lesson_id) WHERE status = 'in_progress';
CREATE INDEX idx_quiz_attempts_enrollment
    ON quiz_attempts (enrollment_id, lesson_id, attempt_no);

-- ---------------------------------------------------------------------------
-- 6) Calibration (1 bảng)
-- ---------------------------------------------------------------------------
CREATE TABLE gaze_calibrations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_fingerprint  VARCHAR(255) NOT NULL,
    model_ubj           BYTEA NOT NULL,
    model_hash          CHAR(64) NOT NULL
                        CONSTRAINT gaze_calibrations_model_hash_check
                        CHECK (model_hash ~ '^[0-9a-f]{64}$'),
    model_version       VARCHAR(64) NOT NULL,
    viewport_width_px   INTEGER NOT NULL
                        CONSTRAINT gaze_calibrations_viewport_width_check
                        CHECK (viewport_width_px > 0),
    viewport_height_px  INTEGER NOT NULL
                        CONSTRAINT gaze_calibrations_viewport_height_check
                        CHECK (viewport_height_px > 0),
    device_pixel_ratio  REAL NOT NULL
                        CONSTRAINT gaze_calibrations_dpr_check
                        CHECK (device_pixel_ratio > 0),
    screen_x_px         INTEGER,
    screen_y_px         INTEGER,
    num_points          INTEGER NOT NULL DEFAULT 25
                        CONSTRAINT gaze_calibrations_num_points_check
                        CHECK (num_points > 0),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_gaze_calibrations_lookup
    ON gaze_calibrations (user_id, device_fingerprint, created_at DESC);

-- ---------------------------------------------------------------------------
-- 7) Phiên học, lượt xem, layout, gaze thô (4 bảng)
-- ---------------------------------------------------------------------------
CREATE TABLE learning_sessions (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enrollment_id          UUID NOT NULL REFERENCES enrollments(id) ON DELETE CASCADE,
    lesson_id              UUID NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    course_visit_id         UUID REFERENCES course_visits(id) ON DELETE CASCADE,
    quiz_attempt_id        UUID REFERENCES quiz_attempts(id) ON DELETE CASCADE,
    calibration_id         UUID REFERENCES gaze_calibrations(id) ON DELETE SET NULL,
    pipeline_version       VARCHAR(64) NOT NULL DEFAULT 'gaze-v1',
    viewport_width_px      INTEGER
                           CONSTRAINT learning_sessions_viewport_width_check
                           CHECK (viewport_width_px IS NULL OR viewport_width_px > 0),
    viewport_height_px     INTEGER
                           CONSTRAINT learning_sessions_viewport_height_check
                           CHECK (viewport_height_px IS NULL OR viewport_height_px > 0),
    calibration_width_px   INTEGER
                           CONSTRAINT learning_sessions_calibration_width_check
                           CHECK (calibration_width_px IS NULL OR calibration_width_px > 0),
    calibration_height_px  INTEGER
                           CONSTRAINT learning_sessions_calibration_height_check
                           CHECK (calibration_height_px IS NULL OR calibration_height_px > 0),
    device_pixel_ratio     REAL
                           CONSTRAINT learning_sessions_dpr_check
                           CHECK (device_pixel_ratio IS NULL OR device_pixel_ratio > 0),
    tracking_consent       BOOLEAN NOT NULL DEFAULT true,
    status                 VARCHAR(16) NOT NULL DEFAULT 'in_progress'
                           CONSTRAINT learning_sessions_status_check
                           CHECK (status IN ('in_progress', 'completed', 'aborted', 'expired')),
    started_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at               TIMESTAMPTZ,
    expires_at             TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_learning_sessions_enrollment
    ON learning_sessions (enrollment_id, started_at);
CREATE INDEX idx_learning_sessions_lesson
    ON learning_sessions (lesson_id, started_at);
CREATE INDEX idx_learning_sessions_visit
    ON learning_sessions (course_visit_id, started_at);
CREATE INDEX idx_learning_sessions_status
    ON learning_sessions (status);

CREATE TABLE content_views (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id             UUID NOT NULL REFERENCES learning_sessions(id) ON DELETE CASCADE,
    slide_id               UUID REFERENCES slides(id) ON DELETE CASCADE,
    surface                VARCHAR(16) NOT NULL
                           CONSTRAINT content_views_surface_check
                           CHECK (surface IN ('lesson', 'quiz')),
    sequence_no            INTEGER NOT NULL
                           CONSTRAINT content_views_sequence_check CHECK (sequence_no >= 0),
    started_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at               TIMESTAMPTZ,
    gaze_count             INTEGER NOT NULL DEFAULT 0
                           CONSTRAINT content_views_gaze_count_check CHECK (gaze_count >= 0),
    on_slide_gaze_count    INTEGER NOT NULL DEFAULT 0
                           CONSTRAINT content_views_on_slide_count_check CHECK (on_slide_gaze_count >= 0),
    tracked_duration_ms    BIGINT NOT NULL DEFAULT 0
                           CONSTRAINT content_views_duration_check CHECK (tracked_duration_ms >= 0),
    fixation_count         INTEGER NOT NULL DEFAULT 0
                           CONSTRAINT content_views_fixation_count_check CHECK (fixation_count >= 0),
    heatmap_grid           JSONB NOT NULL DEFAULT '[]'::jsonb
                           CONSTRAINT content_views_heatmap_check
                           CHECK (jsonb_typeof(heatmap_grid) = 'array'),
    analysis_status        VARCHAR(16) NOT NULL DEFAULT 'pending'
                           CONSTRAINT content_views_analysis_status_check
                           CHECK (analysis_status IN ('pending', 'running', 'ready', 'failed')),
    analysis_version       VARCHAR(64) NOT NULL DEFAULT 'gaze-metrics-v4',
    analyzed_at            TIMESTAMPTZ,
    UNIQUE (session_id, sequence_no)
);
CREATE INDEX idx_content_views_session
    ON content_views (session_id, started_at);
CREATE INDEX idx_content_views_slide
    ON content_views (slide_id);
CREATE INDEX idx_content_views_analysis
    ON content_views (analysis_status);

CREATE TABLE view_layouts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_view_id  UUID NOT NULL REFERENCES content_views(id) ON DELETE CASCADE,
    layout_no        INTEGER NOT NULL
                     CONSTRAINT view_layouts_layout_no_check CHECK (layout_no >= 0),
    coordinate_space VARCHAR(16) NOT NULL DEFAULT 'current-v1'
                     CONSTRAINT view_layouts_coordinate_space_check
                     CHECK (coordinate_space IN ('current-v1', 'original-v1')),
    visible_rect     JSONB NOT NULL DEFAULT '{}'::jsonb
                     CONSTRAINT view_layouts_visible_rect_check
                     CHECK (jsonb_typeof(visible_rect) = 'object'),
    slide_rect       JSONB NOT NULL DEFAULT '{}'::jsonb
                     CONSTRAINT view_layouts_slide_rect_check
                     CHECK (jsonb_typeof(slide_rect) = 'object'),
    elements         JSONB NOT NULL DEFAULT '[]'::jsonb
                     CONSTRAINT view_layouts_elements_check
                     CHECK (jsonb_typeof(elements) = 'array'),
    captured_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (content_view_id, layout_no)
);
CREATE INDEX idx_view_layouts_view ON view_layouts (content_view_id, captured_at);

CREATE TABLE gaze_samples (
    id                BIGSERIAL PRIMARY KEY,
    content_view_id   UUID NOT NULL REFERENCES content_views(id) ON DELETE CASCADE,
    layout_id         UUID REFERENCES view_layouts(id) ON DELETE SET NULL,
    client_batch_id   UUID NOT NULL,
    sequence          BIGINT NOT NULL
                      CONSTRAINT gaze_samples_sequence_check CHECK (sequence >= 0),
    event_time        TIMESTAMPTZ NOT NULL,
    viewport_x        REAL,
    viewport_y        REAL,
    original_viewport_x REAL,
    original_viewport_y REAL,
    slide_x           REAL,
    slide_y           REAL,
    -- Nhãn phân tích duy nhất: "SLIDE_AOI_1", "SLIDE_NO_LABEL",
    -- tên UI AOI, hoặc "UI_NO_LABEL". NULL khi sample không hợp lệ.
    aoi_label         TEXT,
    -- Legacy: giữ để tương thích API/export cũ; sau reanalyze chỉ có 0/1 phần tử.
    aoi_codes         TEXT[] NOT NULL DEFAULT '{}',
    status            VARCHAR(16) NOT NULL
                      CONSTRAINT gaze_samples_status_check
                      CHECK (status IN ('ok', 'no_face', 'error', 'offscreen')),
    quality_flags     JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (content_view_id, client_batch_id, sequence),
    CONSTRAINT gaze_samples_status_coords_check CHECK (
        (status = 'ok' AND viewport_x IS NOT NULL AND viewport_y IS NOT NULL)
        OR (status <> 'ok' AND viewport_x IS NULL AND viewport_y IS NULL)
    ),
    CONSTRAINT gaze_samples_viewport_x_check
        CHECK (viewport_x IS NULL OR (viewport_x > -100 AND viewport_x < 100)),
    CONSTRAINT gaze_samples_viewport_y_check
        CHECK (viewport_y IS NULL OR (viewport_y > -100 AND viewport_y < 100))
);
CREATE INDEX idx_gaze_samples_view_time
    ON gaze_samples (content_view_id, event_time);
CREATE INDEX idx_gaze_samples_event_time
    ON gaze_samples (event_time);
CREATE INDEX idx_gaze_samples_aoi_codes
    ON gaze_samples USING gin (aoi_codes);
CREATE INDEX idx_gaze_samples_aoi_label
    ON gaze_samples (aoi_label)
    WHERE aoi_label IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 8) AOI hiện hành (1 bảng)
-- ---------------------------------------------------------------------------
CREATE TABLE aois (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slide_id        UUID REFERENCES slides(id) ON DELETE CASCADE,
    ui_schema       VARCHAR(64),
    code            VARCHAR(64) NOT NULL,
    name            VARCHAR(100) NOT NULL,
    -- Nhãn phân tích ổn định cho leaf slide: AOI_1, AOI_2, ...
    -- NULL với container, no_label và UI AOI (UI dùng name làm nhãn).
    label           VARCHAR(64),
    parent_id       UUID REFERENCES aois(id) ON DELETE SET NULL,
    geometry        JSONB NOT NULL DEFAULT '{}'::jsonb
                    CONSTRAINT aois_geometry_check CHECK (jsonb_typeof(geometry) = 'object'),
    is_container    BOOLEAN NOT NULL DEFAULT false,
    kind            VARCHAR(16) NOT NULL DEFAULT 'custom'
                    CONSTRAINT aois_kind_check
                    CHECK (kind IN ('text', 'image', 'table', 'drawing', 'custom', 'ui', 'system')),
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT aois_target_check CHECK (
        (slide_id IS NOT NULL AND ui_schema IS NULL)
        OR (slide_id IS NULL AND ui_schema IS NOT NULL)
    )
);
CREATE UNIQUE INDEX ux_aois_slide_code
    ON aois (slide_id, code) WHERE slide_id IS NOT NULL;
CREATE UNIQUE INDEX ux_aois_ui_code
    ON aois (ui_schema, code) WHERE ui_schema IS NOT NULL;
CREATE UNIQUE INDEX ux_aois_slide_label
    ON aois (slide_id, label)
    WHERE slide_id IS NOT NULL AND label IS NOT NULL;
CREATE INDEX idx_aois_slide ON aois (slide_id);
CREATE INDEX idx_aois_parent ON aois (parent_id);

-- ---------------------------------------------------------------------------
-- 9) Chat (2 bảng)
-- ---------------------------------------------------------------------------
CREATE TABLE chat_sessions (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id          UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    lesson_id          UUID REFERENCES lessons(id) ON DELETE CASCADE,
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
-- 10) Metadata hệ thống (1 bảng)
-- ---------------------------------------------------------------------------
CREATE TABLE app_metadata (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 11) View phục vụ outline + chatbot RAG
-- ---------------------------------------------------------------------------
CREATE VIEW v_course_outline AS
SELECT
    c.id                    AS course_id,
    c.title                 AS course_title,
    c.status                AS course_status,
    m.id                    AS module_id,
    m.title                 AS module_title,
    m.position              AS module_position,
    l.id                    AS lesson_id,
    l.kind                  AS lesson_kind,
    l.title                 AS lesson_title,
    l.position              AS lesson_position,
    l.quiz_config,
    s.id                    AS slide_id,
    s.position              AS slide_position,
    s.title                 AS slide_title,
    s.page_number           AS source_page,
    l.pdf_asset_id,
    ma.object_key           AS pdf_object_key,
    ma.storage_backend      AS pdf_storage_backend,
    ma.mime_type            AS pdf_mime_type,
    s.transcript,
    s.embedding,
    s.content_tsv,
    s.index_status,
    s.pipeline_version,
    s.model_version
FROM courses c
JOIN course_modules m ON m.course_id = c.id
JOIN lessons l ON l.module_id = m.id
LEFT JOIN slides s ON s.lesson_id = l.id
LEFT JOIN media_assets ma ON ma.id = l.pdf_asset_id;

CREATE VIEW v_published_course_outline AS
SELECT *
FROM v_course_outline
WHERE course_status = 'published';

CREATE VIEW v_chatbot_slide_documents AS
SELECT *
FROM v_published_course_outline
WHERE slide_id IS NOT NULL
  AND index_status = 'ready';

-- ---------------------------------------------------------------------------
-- 12) Dữ liệu tham chiếu tối thiểu
-- ---------------------------------------------------------------------------
INSERT INTO app_metadata (key, value) VALUES
    ('schema_generation', '12'),
    ('db_instance_id', gen_random_uuid()::text)
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now();
