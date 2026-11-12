-- =============================================================================
-- admin_reader_role.sql — role DB chỉ đọc cho trang Truy vấn CSDL của admin.
--
-- Quyền:
--   - SELECT trên các bảng/view public.
--   - KHÔNG đọc auth_sessions, user_identities.
--   - users: chỉ đọc các cột an toàn (không password_hash).
--   - Không có quyền ghi/DDL.
--
-- Idempotent: tạo role nếu thiếu, cập nhật password, revoke toàn bộ quyền cũ
-- trên schema public rồi grant lại đúng phạm vi.
--
-- Lưu ý: bảng mới thêm sau này cần chạy lại script để được grant SELECT.
--
-- Tham số psql: :'admin_role' :'admin_password' :"dbname"
-- =============================================================================

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'admin_role', :'admin_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'admin_role')
\gexec

SELECT format(
    'ALTER ROLE %I WITH LOGIN PASSWORD %L '
    'NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',
    :'admin_role',
    :'admin_password'
)
WHERE EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'admin_role')
\gexec

GRANT CONNECT ON DATABASE :"dbname" TO :"admin_role";
GRANT USAGE ON SCHEMA public TO :"admin_role";

-- Xóa mọi quyền cũ (kể cả grant từ schema cũ) trước khi grant lại.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM :"admin_role";
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM :"admin_role";

-- Đọc tất cả bảng/view public.
GRANT SELECT ON ALL TABLES IN SCHEMA public TO :"admin_role";

-- Không cho đọc bảng chứa token/identity.
REVOKE ALL ON auth_sessions, user_identities FROM :"admin_role";

-- users: chỉ grant các cột an toàn, không grant password_hash.
REVOKE ALL ON users FROM :"admin_role";
GRANT SELECT (id, email, status, last_login_at, created_at, deleted_at)
    ON users TO :"admin_role";

-- Không cho đọc bảng migration nội bộ.
REVOKE ALL ON schema_migrations FROM :"admin_role";

-- Cấu hình an toàn cho role (app cũng set qua server_settings).
ALTER ROLE :"admin_role" SET default_transaction_read_only = on;
ALTER ROLE :"admin_role" SET statement_timeout = '10s';
ALTER ROLE :"admin_role" SET lock_timeout = '2s';
ALTER ROLE :"admin_role" SET idle_in_transaction_session_timeout = '15s';
ALTER ROLE :"admin_role" SET search_path = public;
