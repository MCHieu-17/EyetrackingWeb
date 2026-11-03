-- 025_course_require_calibration.sql
--
-- Cờ cấp KHÓA HỌC: có bắt buộc sinh viên kiểm tra camera + hiệu chỉnh điểm nhìn
-- trước khi vào học hay không.
--
--   true  (mặc định): giữ hành vi cũ — phải qua preflight/calibration.
--   false           : sinh viên vào thẳng trang học; không bật camera, không ghi
--                     gaze. Dùng khi dev không có camera hoặc không cần dữ liệu
--                     điểm nhìn cho khóa đó.
--
-- Idempotent: chạy lại nhiều lần an toàn.

ALTER TABLE courses
    ADD COLUMN IF NOT EXISTS require_calibration BOOLEAN NOT NULL DEFAULT true;
