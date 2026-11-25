-- 008_course_camera_preview.sql
-- Cờ cấp KHÓA HỌC: hiển thị khung xem trước camera cho sinh viên trong lúc học.
--
-- Khung chỉ đọc lại `MediaStream` mà gaze tracker đã mở để ghi gaze, nên bật
-- cờ không mở thêm camera, không suy luận thêm và không ghi thêm dữ liệu.
--
-- Không thêm bảng/cột dẫn xuất nào khác; 24 bảng lõi và schema_generation
-- '13' giữ nguyên.

ALTER TABLE courses
    ADD COLUMN IF NOT EXISTS show_camera_preview BOOLEAN NOT NULL DEFAULT false;
