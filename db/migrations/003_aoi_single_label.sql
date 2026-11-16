-- 003_aoi_single_label.sql
-- Mỗi gaze sample chỉ còn một nhãn AOI trong `gaze_samples.aoi_label`.
-- Bỏ mảng `aoi_codes` (legacy 0/1 phần tử) và cache gợi ý vùng sinh từ PDF
-- trên `slides.aoi_suggestions`; giáo viên tự vẽ vùng trong trình soạn AOI.

DROP INDEX IF EXISTS idx_gaze_samples_aoi_codes;

ALTER TABLE gaze_samples
    DROP COLUMN IF EXISTS aoi_codes;

ALTER TABLE slides
    DROP COLUMN IF EXISTS aoi_suggestions;
