-- =====================================================================
-- seed_dev_users.sql — TÀI KHOẢN MẪU CHO DEV (KHÔNG chạy tự động).
--
-- Chạy thủ công:
--     ./scripts/seed_dev.sh
--
-- Mật khẩu mặc định: Password123!
-- Quy tắc: KHÔNG ghi đè mật khẩu của tài khoản đã tồn tại. Chỉ tạo user/profile
-- còn thiếu; role grant idempotent.
-- =====================================================================

-- ---------------------------------------------------------------------
-- ADMIN
-- ---------------------------------------------------------------------
INSERT INTO users (email, password_hash, status, must_change_password)
SELECT 'admin@school.edu.vn',
       '$2b$12$1q/iiUi4DF25DxUvlvyt5uUDwDBsEpGbTj5SqkEudV9QZCQhwYDoq',
       'active',
       false
WHERE NOT EXISTS (
    SELECT 1 FROM users WHERE lower(email) = lower('admin@school.edu.vn')
);

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u JOIN roles r ON r.code = 'admin'
WHERE lower(u.email) = lower('admin@school.edu.vn')
ON CONFLICT DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, gender)
SELECT u.id, 'Quản Trị Viên Hệ Thống', 'male'
FROM users u
WHERE lower(u.email) = lower('admin@school.edu.vn')
ON CONFLICT (user_id) DO NOTHING;

-- ---------------------------------------------------------------------
-- GIÁO VIÊN
-- ---------------------------------------------------------------------
INSERT INTO users (email, password_hash, status, must_change_password)
SELECT 'teacher@school.edu.vn',
       '$2b$12$1q/iiUi4DF25DxUvlvyt5uUDwDBsEpGbTj5SqkEudV9QZCQhwYDoq',
       'active',
       false
WHERE NOT EXISTS (
    SELECT 1 FROM users WHERE lower(email) = lower('teacher@school.edu.vn')
);

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u JOIN roles r ON r.code = 'teacher'
WHERE lower(u.email) = lower('teacher@school.edu.vn')
ON CONFLICT DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, gender)
SELECT u.id, 'Giáo Viên Mẫu', 'female'
FROM users u
WHERE lower(u.email) = lower('teacher@school.edu.vn')
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO teacher_profiles (user_id, teacher_code, department)
SELECT u.id, 'GV0001', 'Khoa Công Nghệ Thông Tin'
FROM users u
WHERE lower(u.email) = lower('teacher@school.edu.vn')
ON CONFLICT (user_id) DO NOTHING;

-- ---------------------------------------------------------------------
-- SINH VIÊN
-- ---------------------------------------------------------------------
INSERT INTO users (email, password_hash, status, must_change_password)
SELECT 'student@school.edu.vn',
       '$2b$12$1q/iiUi4DF25DxUvlvyt5uUDwDBsEpGbTj5SqkEudV9QZCQhwYDoq',
       'active',
       false
WHERE NOT EXISTS (
    SELECT 1 FROM users WHERE lower(email) = lower('student@school.edu.vn')
);

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u JOIN roles r ON r.code = 'student'
WHERE lower(u.email) = lower('student@school.edu.vn')
ON CONFLICT DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, gender)
SELECT u.id, 'Sinh Viên Mẫu', 'male'
FROM users u
WHERE lower(u.email) = lower('student@school.edu.vn')
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO student_profiles (user_id, student_code, program)
SELECT u.id, 'SV0001', 'Công Nghệ Thông Tin K20'
FROM users u
WHERE lower(u.email) = lower('student@school.edu.vn')
ON CONFLICT (user_id) DO NOTHING;
