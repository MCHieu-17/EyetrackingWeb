-- =============================================================================
-- 003_slide_pdf_storage.sql — chuyển slide sang lưu PDF gốc.
--
-- * Mỗi lần upload chỉ lưu một PDF chuẩn hóa (source.pdf); không lưu JPG.
-- * Mỗi trang PDF là một slide_version với source_page tương ứng.
-- * Thêm slide_import_jobs cho pipeline upload/convert bất đồng bộ.
-- * Bỏ hoàn toàn image_asset_id; view chỉ còn tham chiếu PDF.
-- * Đánh dấu asset JPG cũ là deleted để script cleanup xóa khỏi storage.
-- =============================================================================

DROP VIEW IF EXISTS v_chatbot_slide_documents;
DROP VIEW IF EXISTS v_published_course_outline;

-- ---------------------------------------------------------------------------
-- 1) Media assets: phân biệt PDF chuẩn hóa và metadata
-- ---------------------------------------------------------------------------
ALTER TABLE media_assets
    ADD COLUMN kind VARCHAR(16) NOT NULL DEFAULT 'source'
        CONSTRAINT media_assets_kind_check
        CHECK (kind IN ('source', 'normalized', 'thumbnail')),
    ADD COLUMN metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

-- ---------------------------------------------------------------------------
-- 2) Job queue cho upload/convert slide
-- ---------------------------------------------------------------------------
CREATE TABLE slide_import_jobs (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id          UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    lesson_id          UUID NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    lesson_version_id  UUID NOT NULL REFERENCES lesson_versions(id) ON DELETE CASCADE,
    created_by         UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    status             VARCHAR(16) NOT NULL DEFAULT 'queued'
                       CONSTRAINT slide_import_jobs_status_check
                       CHECK (status IN ('queued', 'processing', 'ready', 'failed', 'cancelled')),
    source_filename    TEXT NOT NULL,
    source_mime        VARCHAR(127) NOT NULL,
    source_size        BIGINT NOT NULL
                       CONSTRAINT slide_import_jobs_source_size_check
                       CHECK (source_size >= 0),
    source_sha256      CHAR(64) NOT NULL
                       CONSTRAINT slide_import_jobs_source_sha256_check
                       CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
    source_object_key  TEXT NOT NULL,
    pdf_asset_id       UUID REFERENCES media_assets(id) ON DELETE RESTRICT,
    page_count         INTEGER
                       CONSTRAINT slide_import_jobs_page_count_check
                       CHECK (page_count IS NULL OR page_count > 0),
    error              TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at         TIMESTAMPTZ,
    finished_at        TIMESTAMPTZ
);
CREATE INDEX idx_slide_import_jobs_status
    ON slide_import_jobs (status, created_at);
CREATE INDEX idx_slide_import_jobs_lesson
    ON slide_import_jobs (lesson_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- 3) Slide versions: chỉ còn PDF + số trang
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM slide_versions
        WHERE source_pdf_asset_id IS NULL OR source_page IS NULL
    ) THEN
        RAISE EXCEPTION
            'slide_versions còn source_pdf_asset_id/source_page NULL; hãy reset DB hoặc chạy cleanup trước';
    END IF;
END $$;

ALTER TABLE slide_versions DROP COLUMN image_asset_id;
ALTER TABLE slide_versions ALTER COLUMN source_pdf_asset_id SET NOT NULL;
ALTER TABLE slide_versions ALTER COLUMN source_page SET NOT NULL;
CREATE INDEX idx_slide_versions_source_pdf
    ON slide_versions (source_pdf_asset_id, source_page);

-- Đánh dấu JPG cũ để script cleanup xóa khỏi storage. Giữ thumbnail nếu có.
UPDATE media_assets
SET state = 'deleted'
WHERE mime_type LIKE 'image/%'
  AND state <> 'deleted'
  AND id NOT IN (
      SELECT thumbnail_asset_id
      FROM course_versions
      WHERE thumbnail_asset_id IS NOT NULL
  );

-- ---------------------------------------------------------------------------
-- 4) Views: chỉ dùng PDF asset
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
    sv.source_pdf_asset_id  AS pdf_asset_id,
    ma.object_key           AS pdf_object_key,
    ma.storage_backend      AS pdf_storage_backend,
    ma.mime_type            AS pdf_mime_type,
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
  ON ma.id = sv.source_pdf_asset_id
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
    o.pdf_asset_id,
    o.pdf_object_key,
    o.pdf_storage_backend,
    o.pdf_mime_type,
    o.source_page,
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
