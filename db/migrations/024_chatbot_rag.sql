-- 024_chatbot_rag.sql
--
-- Dựng lại schema cho trợ lý học tập RAG (chatbot) sau khi 023 đã gỡ bản cũ.
--
-- Thay đổi so với bản cũ:
--   * Embedding 1024 chiều (Qwen3-Embedding-0.6B) + HNSW cosine.
--   * Thêm `content_tsv` (Postgres FTS) để hybrid search BM25 + vector.
--   * `lesson_content_embedding` lưu thêm course_id/lesson_id/metadata để
--     truy hồi nhanh trong đúng một môn và dựng citation đầy đủ.
--   * `chat_sessions`/`chat_messages` giữ nguyên shape cũ, thêm index cần thiết.
--
-- Idempotent: chạy lại nhiều lần an toàn. Runner chỉ chạy file chưa áp, nhưng
-- mọi file vẫn phải idempotent để DB cũ chưa có schema_migrations chạy được.

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- unaccent() không immutable nên không dùng trực tiếp trong generated column.
-- Wrapper này chuẩn hoá dấu tiếng Việt + đ→d để FTS khớp cả khi người dùng
-- gõ không dấu.
CREATE OR REPLACE FUNCTION immutable_unaccent(text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
STRICT
AS $$
    SELECT translate(unaccent('unaccent', $1), 'đĐ', 'dD');
$$;

-- Trạng thái ingest của từng slide (backend hiển thị badge lỗi cho giáo viên).
ALTER TABLE lesson_contents
    ADD COLUMN IF NOT EXISTS embedding_status VARCHAR(10) NOT NULL DEFAULT 'none';
ALTER TABLE lesson_contents
    ADD COLUMN IF NOT EXISTS embedding_error TEXT;
ALTER TABLE lesson_contents
    ADD COLUMN IF NOT EXISTS embedding_updated_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_lesson_contents_embedding_status
    ON lesson_contents(embedding_status);

-- Một dòng / slide. `content` là transcript VLM (Markdown); `content_tsv` là
-- generated column phục vụ nhánh keyword của hybrid search.
CREATE TABLE IF NOT EXISTS lesson_content_embedding (
    lesson_content_id UUID PRIMARY KEY REFERENCES lesson_contents(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    lesson_id UUID NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    content_tsv TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('simple', immutable_unaccent(content))
    ) STORED,
    embedding VECTOR(1024) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Phòng trường hợp bảng đã tồn tại từ một lần chạy dở trước đó.
ALTER TABLE lesson_content_embedding
    ADD COLUMN IF NOT EXISTS content_tsv TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('simple', immutable_unaccent(content))
    ) STORED;
ALTER TABLE lesson_content_embedding
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE lesson_content_embedding
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE lesson_content_embedding
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_lesson_content_embedding_course
    ON lesson_content_embedding(course_id);
CREATE INDEX IF NOT EXISTS idx_lesson_content_embedding_lesson
    ON lesson_content_embedding(lesson_id);
CREATE INDEX IF NOT EXISTS idx_lesson_content_embedding_tsv
    ON lesson_content_embedding USING gin (content_tsv);
CREATE INDEX IF NOT EXISTS idx_lesson_content_embedding_hnsw
    ON lesson_content_embedding USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Lịch sử chat hiển thị cho sinh viên. Chatbot service không ghi bảng này;
-- backend là nguồn sự thật và gửi history sang chatbot theo từng request.
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    lesson_id UUID REFERENCES lessons(id) ON DELETE SET NULL,
    assignment_id UUID REFERENCES quiz_assignments(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL DEFAULT 'Phiên mới',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_student_course
    ON chat_sessions (student_id, course_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(10) NOT NULL CHECK (role IN ('student', 'assistant')),
    content TEXT NOT NULL,
    citations JSONB NOT NULL DEFAULT '[]'::jsonb,
    intent VARCHAR(30),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chat_messages_citations_array CHECK (jsonb_typeof(citations) = 'array')
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session
    ON chat_messages (session_id, created_at);

COMMIT;
