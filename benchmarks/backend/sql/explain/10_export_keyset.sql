-- Export JSONL: một page keyset trong một content view (Đợt 6).
-- Query khớp backend/app/services/analysis/export.py::SAMPLE_SQL.
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS)
SELECT
    gs.id, gs.event_time, gs.sequence, gs.client_batch_id,
    gs.viewport_x, gs.viewport_y, gs.slide_x, gs.slide_y,
    gs.aoi_label, gs.status, gs.quality_flags,
    cv.id AS content_view_id, cv.sequence_no AS view_sequence,
    ls.tracking_consent, ls.id AS session_id, ls.enrollment_id,
    l.id AS lesson_id, l.title AS lesson_title,
    s.id AS slide_id, s.title AS slide_title, s.page_number
FROM gaze_samples gs
JOIN content_views cv ON cv.id = gs.content_view_id
JOIN learning_sessions ls ON ls.id = cv.session_id
JOIN lessons l ON l.id = ls.lesson_id
LEFT JOIN slides s ON s.id = cv.slide_id
WHERE cv.id = :'core_view_id'::uuid
ORDER BY gs.event_time, gs.id
LIMIT 1000;

-- Page kế tiếp trong cùng view (keyset event_time,id).
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS)
SELECT gs.id, gs.event_time
FROM gaze_samples gs
WHERE gs.content_view_id = :'core_view_id'::uuid
  AND (gs.event_time, gs.id) > ('epoch'::timestamptz, 0)
ORDER BY gs.event_time, gs.id
LIMIT 1000;
