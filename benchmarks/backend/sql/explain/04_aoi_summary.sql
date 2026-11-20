-- Query nền của POST /teacher/courses/{id}/analytics/aoi-summary.
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS)
SELECT
    cv.id,
    cv.tracked_duration_ms,
    cv.gaze_count,
    cv.on_slide_gaze_count,
    cv.aoi_stats,
    ls.id AS session_id,
    l.id AS lesson_id,
    s.id AS slide_id,
    e.id AS enrollment_id,
    u.id AS student_id,
    sp.student_code,
    v.id AS visit_id,
    extract(epoch FROM (
        coalesce(cv.ended_at, ls.ended_at, v.ended_at, now()) - cv.started_at
    )) * 1000 AS dwell_ms
FROM content_views cv
JOIN learning_sessions ls ON ls.id = cv.session_id
JOIN lessons l ON l.id = ls.lesson_id
LEFT JOIN slides s ON s.id = cv.slide_id
JOIN enrollments e ON e.id = ls.enrollment_id
JOIN users u ON u.id = e.student_id
LEFT JOIN student_profiles sp ON sp.user_id = u.id
LEFT JOIN course_visits v ON v.id = ls.course_visit_id
WHERE e.course_id = :'core_course_id'::uuid
  AND e.status <> 'dropped';
