-- GET /teacher/visits/{id}/gaze: keyset qua danh sách content view của visit
-- (Đợt 6). Query khớp backend/app/api/routes/analytics.py::list_visit_gaze.
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS)
SELECT
    gs.id, gs.event_time, gs.sequence, gs.viewport_x, gs.viewport_y,
    gs.slide_x, gs.slide_y, gs.aoi_label, gs.status, gs.quality_flags,
    cv.id AS content_view_id, ls.id AS session_id, ls.enrollment_id,
    l.id AS lesson_id, l.title AS lesson_title,
    s.id AS slide_id, s.title AS slide_title, s.page_number
FROM gaze_samples gs
JOIN content_views cv ON cv.id = gs.content_view_id
JOIN learning_sessions ls ON ls.id = cv.session_id
JOIN lessons l ON l.id = ls.lesson_id
LEFT JOIN slides s ON s.id = cv.slide_id
WHERE gs.content_view_id = ANY(ARRAY(
        SELECT cv2.id
        FROM learning_sessions ls2
        JOIN content_views cv2 ON cv2.session_id = ls2.id
        WHERE ls2.course_visit_id = :'core_visit_id'::uuid
    )::uuid[])
  AND (gs.event_time, gs.id) > ('epoch'::timestamptz, 0)
ORDER BY gs.event_time, gs.id
LIMIT 1000;
