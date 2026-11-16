-- =============================================================================
-- chatbot_role.sql — role DB hạn chế cho chatbot RAG (schema generation 13).
--
-- Quyền:
--   - SELECT outline (index cả nháp) + view published;
--   - SELECT và UPDATE các cột index trên `slides`;
--   - KHÔNG đọc users/enrollments/quiz_attempts/chat_*.
-- =============================================================================

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'role', :'password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role')
\gexec

SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'role', :'password')
WHERE EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role')
\gexec

GRANT CONNECT ON DATABASE :"dbname" TO :"role";
GRANT USAGE ON SCHEMA public TO :"role";

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM :"role";
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM :"role";

GRANT SELECT ON v_published_course_outline TO :"role";
GRANT SELECT ON v_course_outline TO :"role";
GRANT SELECT ON v_chatbot_slide_documents TO :"role";
GRANT SELECT ON slides TO :"role";
GRANT UPDATE (
    transcript, embedding, index_status, index_error,
    pipeline_version, model_version, updated_at
) ON slides TO :"role";

REVOKE ALL ON users, auth_sessions, email_otps, enrollments,
    quiz_attempts, learning_sessions, chat_sessions, chat_messages
    FROM :"role";
