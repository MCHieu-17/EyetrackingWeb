-- 004_content_view_aoi_stats.sql
-- Thống kê dẫn xuất theo từng nhãn AOI cho dashboard giáo viên.
--
-- `content_views.aoi_stats` lưu tổng thời lượng và số mẫu hợp lệ của mỗi
-- nhãn AOI trong một lượt xem, dạng:
--   {"SLIDE_AOI_THANHCHAT": {"ms": 1234, "samples": 45}}
--
-- Worker metrics tính lại cột này mỗi lần phân tích, nên đây là dữ liệu dẫn
-- xuất có thể tái tạo. Không thêm bảng mới; 24 bảng lõi giữ nguyên.

ALTER TABLE content_views
    ADD COLUMN IF NOT EXISTS aoi_stats JSONB NOT NULL DEFAULT '{}'::jsonb;
