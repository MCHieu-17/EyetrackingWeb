-- 009_gaze_samples_layout_index.sql
-- FK gaze_samples.layout_id ON DELETE SET NULL không có index khiến mỗi lần
-- xoá view_layout phải seq scan toàn bộ gaze_samples (~2 GB ở dev). Khi xoá
-- khoá học, cascade qua nhiều layout sẽ vượt statement_timeout của API.
-- Index này chỉ thêm index, không thêm bảng/cột; schema_generation giữ '13'.

CREATE INDEX IF NOT EXISTS idx_gaze_samples_layout_id
    ON gaze_samples (layout_id);
