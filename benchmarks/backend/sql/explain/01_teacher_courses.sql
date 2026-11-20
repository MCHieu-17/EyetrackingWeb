-- Tổng hợp attention/sessions cho teacher course list.
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS)
SELECT
    cm.course_id,
    sum(cv.on_slide_gaze_count),
    sum(cv.gaze_count),
    count(ls.id)
FROM course_modules cm
JOIN lessons l ON l.module_id = cm.id
JOIN learning_sessions ls ON ls.lesson_id = l.id
JOIN content_views cv ON cv.session_id = ls.id
WHERE cm.course_id = :'core_course_id'::uuid
  AND cv.surface = 'lesson'
  AND cv.analysis_version = 'gaze-metrics-v8'
GROUP BY cm.course_id;
