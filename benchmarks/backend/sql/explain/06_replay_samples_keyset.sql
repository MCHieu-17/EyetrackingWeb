-- Keyset samples cho replay (trang đầu).
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS)
SELECT id, event_time, sequence, status, viewport_x, viewport_y,
       slide_x, slide_y, aoi_label, quality_flags
FROM gaze_samples
WHERE content_view_id = :'core_view_id'::uuid
ORDER BY event_time, id
LIMIT 2000;
