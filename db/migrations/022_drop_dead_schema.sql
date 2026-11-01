-- 022_drop_dead_schema.sql
--
-- Dọn các bảng/cột không còn code nào đọc/ghi:
--   - Bảng: oauth_accounts, role_permissions, permissions
--   - Cột: user_profiles.email, users.phone, student_profiles.extra,
--          teacher_profiles.extra, lessons.metadata, aoi_regions.created_by,
--          lessons.content_url
--
-- CẨN THẬN: DROP COLUMN là thao tác không thể hoàn tác. Backup DB trước khi
-- chạy trên production:
--   pg_dump -Fc "$DATABASE_URL" > backup_before_022.dump
--
-- Idempotent: chạy lại nhiều lần an toàn.

BEGIN;

-- Bảng chết (role_permissions phụ thuộc permissions nên xóa trước).
DROP TABLE IF EXISTS role_permissions;
DROP TABLE IF EXISTS permissions;
DROP TABLE IF EXISTS oauth_accounts;

-- Cột chết.
ALTER TABLE user_profiles DROP COLUMN IF EXISTS email;
ALTER TABLE users DROP COLUMN IF EXISTS phone;
ALTER TABLE student_profiles DROP COLUMN IF EXISTS extra;
ALTER TABLE teacher_profiles DROP COLUMN IF EXISTS extra;
ALTER TABLE lessons DROP COLUMN IF EXISTS metadata;
ALTER TABLE aoi_regions DROP COLUMN IF EXISTS created_by;
ALTER TABLE lessons DROP COLUMN IF EXISTS content_url;

COMMIT;
