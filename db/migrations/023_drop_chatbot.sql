-- 023_drop_chatbot.sql
--
-- Gỡ toàn bộ schema của dịch vụ chatbot đã bị xoá khỏi repo:
--   - chat_sessions / chat_messages (lịch sử trợ lý học tập)
--   - lesson_content_embedding + các cột embedding_* trên lesson_contents
--   - bảng checkpoint* do LangGraph tự tạo lúc runtime
--   - extension pgvector (chỉ chatbot dùng)
--
-- Idempotent: chạy lại nhiều lần an toàn. Trên DB mới (chưa từng có chatbot),
-- file này không làm gì ngoài việc bảo đảm các đối tượng trên không tồn tại.

BEGIN;

-- Bảng lịch sử chat (xoá bảng con trước để không vướng khóa ngoại).
DROP TABLE IF EXISTS chat_messages;
DROP TABLE IF EXISTS chat_sessions;

-- Bảng vector và trạng thái embedding của slide.
DROP TABLE IF EXISTS lesson_content_embedding;
ALTER TABLE lesson_contents DROP COLUMN IF EXISTS embedding_status;
ALTER TABLE lesson_contents DROP COLUMN IF EXISTS embedding_error;
ALTER TABLE lesson_contents DROP COLUMN IF EXISTS embedding_updated_at;

-- LangGraph PostgresSaver tạo các bảng checkpoint* khi chatbot khởi động.
DO $$
DECLARE
    tbl text;
BEGIN
    FOR tbl IN
        SELECT tablename
          FROM pg_tables
         WHERE schemaname = 'public'
           AND tablename LIKE 'checkpoint%'
    LOOP
        EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', tbl);
    END LOOP;
END $$;

-- pgvector chỉ được dùng cho bảng embedding của chatbot.
DROP EXTENSION IF EXISTS vector;

COMMIT;
