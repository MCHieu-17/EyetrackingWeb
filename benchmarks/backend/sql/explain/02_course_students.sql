-- Roster + metric aggregation theo enrollment/slide.
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS)
SELECT
    cv.slide_id,
    ls.enrollment_id,
    coalesce(sum(cv.gaze_count), 0),
    coalesce(sum(cv.on_slide_gaze_count), 0),
    coalesce(sum(cv.tracked_duration_ms), 0)
FROM content_views cv
JOIN learning_sessions ls ON ls.id = cv.session_id
JOIN enrollments e ON e.id = ls.enrollment_id
WHERE e.course_id = :'core_course_id'::uuid
  AND cv.slide_id IS NOT NULL
  AND cv.analysis_version = 'gaze-metrics-v8'
GROUP BY cv.slide_id, ls.enrollment_id;
