-- =============================================================================
-- 002_reference_seed.sql — dữ liệu tham chiếu tối thiểu.
--
-- Chỉ roles + cấu hình hệ thống. KHÔNG tạo tài khoản mẫu; seed development nằm
-- ở db/seed_dev_users.sql và chỉ chạy khi được chọn.
-- =============================================================================

INSERT INTO roles (code, label) VALUES
    ('admin',   'Quản trị viên'),
    ('teacher', 'Giáo viên'),
    ('student', 'Học sinh')
ON CONFLICT (code) DO NOTHING;

INSERT INTO calibration_settings (id, enabled, threshold)
VALUES (1, true, 0.12)
ON CONFLICT (id) DO NOTHING;

INSERT INTO app_metadata (key, value) VALUES
    ('schema_generation', '1')
ON CONFLICT (key) DO NOTHING;
