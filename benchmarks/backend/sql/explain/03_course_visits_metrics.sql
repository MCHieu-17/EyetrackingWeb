-- Metric aggregation cho page course visits.
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS)
SELECT
    ls.course_visit_id,
    coalesce(sum(cv.gaze_count), 0),
    coalesce(sum(cv.on_slide_gaze_count), 0),
    coalesce(sum(cv.tracked_duration_ms), 0)
FROM content_views cv
JOIN learning_sessions ls ON ls.id = cv.session_id
JOIN course_visits v ON v.id = ls.course_visit_id
WHERE v.enrollment_id IN (
    SELECT id FROM enrollments WHERE course_id = :'core_course_id'::uuid
)
GROUP BY ls.course_visit_id;
