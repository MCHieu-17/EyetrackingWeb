-- =====================================================================
-- seed_dev_users.sql — TÀI KHOẢN MẪU CHO DEV (KHÔNG chạy tự động).
--
-- Mật khẩu mặc định: Password123!
-- Schema generation 13: role nằm trực tiếp trên users, hồ sơ cơ bản cũng ở users.
-- =====================================================================

-- ADMIN
INSERT INTO users (email, password_hash, role, status, full_name, gender)
VALUES (
    'admin@school.edu.vn',
    '$2b$12$1q/iiUi4DF25DxUvlvyt5uUDwDBsEpGbTj5SqkEudV9QZCQhwYDoq',
    'admin', 'active', 'Quản Trị Viên Hệ Thống', 'male'
)
ON CONFLICT (lower(email)) DO NOTHING;

-- GIÁO VIÊN
INSERT INTO users (email, password_hash, role, status, full_name, gender)
VALUES (
    'teacher@school.edu.vn',
    '$2b$12$1q/iiUi4DF25DxUvlvyt5uUDwDBsEpGbTj5SqkEudV9QZCQhwYDoq',
    'teacher', 'active', 'Giáo Viên Mẫu', 'female'
)
ON CONFLICT (lower(email)) DO NOTHING;

INSERT INTO teacher_profiles (user_id, teacher_code, department)
SELECT u.id, 'GV0001', 'Khoa Công Nghệ Thông Tin'
FROM users u
WHERE lower(u.email) = lower('teacher@school.edu.vn')
ON CONFLICT (user_id) DO NOTHING;

-- SINH VIÊN
INSERT INTO users (email, password_hash, role, status, full_name, gender)
VALUES (
    'student@school.edu.vn',
    '$2b$12$1q/iiUi4DF25DxUvlvyt5uUDwDBsEpGbTj5SqkEudV9QZCQhwYDoq',
    'student', 'active', 'Sinh Viên Mẫu', 'male'
)
ON CONFLICT (lower(email)) DO NOTHING;

INSERT INTO student_profiles (user_id, student_code, program)
SELECT u.id, 'SV0001', 'Công Nghệ Thông Tin K20'
FROM users u
WHERE lower(u.email) = lower('student@school.edu.vn')
ON CONFLICT (user_id) DO NOTHING;
