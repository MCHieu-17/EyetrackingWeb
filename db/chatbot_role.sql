-- =============================================================================
-- chatbot_role.sql — role DB hạn chế cho chatbot RAG.
--
-- Được gọi tự động bởi db/migrate.sh sau khi áp migrations (khi
-- CHATBOT_DB_USER + CHATBOT_DB_PASSWORD có trong môi trường), và có thể chạy
-- tay qua scripts/create_chatbot_role.sh.
--
-- Quyền:
--   - SELECT view published + view outline draft (index trước khi xuất bản);
--   - SELECT/INSERT/UPDATE/DELETE slide_documents (transcript + embedding);
--   - KHÔNG đọc quiz_specs/quiz_attempts/users/chat_*.
--
-- Idempotent: tạo role nếu thiếu, cập nhật password, revoke toàn bộ quyền cũ
-- trên schema public rồi grant lại đúng phạm vi.
--
-- Tham số psql: :'role' :'password' :'dbname'
-- =============================================================================

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'role', :'password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role')
\gexec

SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'role', :'password')
WHERE EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role')
\gexec

GRANT CONNECT ON DATABASE :"dbname" TO :"role";
GRANT USAGE ON SCHEMA public TO :"role";

-- Xóa mọi quyền cũ (kể cả grant từ schema cũ) trước khi grant lại.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM :"role";
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM :"role";

-- Đọc nội dung published qua view; đọc outline draft để index trước khi
-- xuất bản; ghi tài liệu ingest.
GRANT SELECT ON v_published_course_outline TO :"role";
GRANT SELECT ON v_course_outline TO :"role";
GRANT SELECT ON v_chatbot_slide_documents TO :"role";
GRANT SELECT ON slide_documents TO :"role";
GRANT INSERT, UPDATE, DELETE ON slide_documents TO :"role";

-- Không cho đọc dữ liệu bài tập/người dùng/chat.
REVOKE ALL ON quiz_specs, quiz_attempts, users, chat_sessions, chat_messages
    FROM :"role";
