-- Heatmap một slide: view + heatmap_grid + EXISTS gaze sample.
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS)
SELECT cv.gaze_count, cv.heatmap_grid, cv.analysis_status,
       cv.analysis_version,
       exists (
           SELECT 1 FROM gaze_samples gs WHERE gs.content_view_id = cv.id
       ) AS has_samples
FROM content_views cv
JOIN learning_sessions ls ON ls.id = cv.session_id
JOIN enrollments e ON e.id = ls.enrollment_id
WHERE e.course_id = :'core_course_id'::uuid
  AND cv.slide_id = :'core_slide_id'::uuid;
