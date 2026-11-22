-- 006_gaze_sample_indexes.sql
-- Giảm write amplification khi ghi gaze: `event_time` là cột append-only và
-- chỉ dùng cho retention/export theo khoảng thời gian, nên BRIN phù hợp hơn
-- btree. Index btree cũ tốn ~166 MB và gần như không được dùng khi insert.
--
-- Không thêm bảng/cột; schema_generation giữ nguyên '13'.

DROP INDEX IF EXISTS idx_gaze_samples_event_time;

CREATE INDEX IF NOT EXISTS idx_gaze_samples_event_time_brin
    ON gaze_samples USING brin (event_time)
    WITH (pages_per_range = 32, autosummarize = on);
