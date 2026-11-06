-- =====================================================================
-- BẢO TRÌ PARTITION gaze_samples — tạo partition tháng mới.
-- Function create_gaze_sample_partitions() định nghĩa trong
-- db/migrations/001_baseline.sql (phải chạy baseline trước).
--
-- Chạy thủ công:
--   psql -d eyetracking -f ops/maintain_partitions.sql
--
-- Không xoá partition cũ. Dữ liệu rơi ngoài các tháng đã tạo vào
-- gaze_samples_default (không mất, nhưng nên xử lý sớm).
-- =====================================================================

SELECT create_gaze_sample_partitions(3);
