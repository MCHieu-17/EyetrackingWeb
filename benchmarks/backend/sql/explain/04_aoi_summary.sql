-- Query nền của POST /teacher/courses/{id}/analytics/aoi-summary.
-- Ba statement dưới đây khớp implementation trong
-- backend/app/services/analytics/summary.py (_totals_stmt/_base_rows_stmt/
-- _label_rows_stmt): chỉ đọc cột cần, aggregate bằng SQL thay vì hydrate ORM.

-- (1) Totals + short/stale count.
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS)
SELECT
    count(*) AS content_view_count,
    count(*) FILTER (WHERE views.dwell_ms < 1000) AS short_view_count,
    count(DISTINCT views.visit_key) AS visit_count,
    count(DISTINCT views.student_id) AS student_count,
    coalesce(sum(views.tracked_duration_ms), 0) AS tracked_ms,
    coalesce(sum(views.gaze_count), 0) AS gaze_count,
    coalesce(sum(views.on_slide_gaze_count), 0) AS on_slide_count,
    count(*) FILTER (
        WHERE views.analysis_status <> 'ready'
           OR views.analysis_version <> 'gaze-metrics-v8'
           OR (views.gaze_count > 0 AND views.aoi_stats = '{}'::jsonb)
    ) AS stale_view_count
FROM (
    SELECT
        cv.id AS view_id,
        l.id AS lesson_id,
        s.id AS slide_id,
        e.status AS enrollment_status,
        u.id AS student_id,
        coalesce(nullif(u.full_name, ''), u.email) AS student_name,
        coalesce(sp.student_code, '') AS student_code,
        coalesce(v.id::text, 'session:' || ls.id::text) AS visit_key,
        cv.tracked_duration_ms,
        cv.gaze_count,
        cv.on_slide_gaze_count,
        cv.aoi_stats,
        cv.analysis_status,
        cv.analysis_version,
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
      AND e.status <> 'dropped'
) AS views;

-- (2) Hàng nền theo nhóm (view không có AOI vẫn phải xuất hiện).
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS)
SELECT
    grouping(views.lesson_id) AS g_lesson,
    grouping(views.slide_id) AS g_slide,
    grouping(views.student_id) AS g_student,
    grouping(views.visit_key) AS g_visit,
    views.lesson_id,
    views.lesson_title,
    views.lesson_kind,
    views.slide_id,
    views.slide_title,
    views.page_number,
    views.student_id,
    views.student_name,
    views.student_code,
    views.enrollment_status,
    views.visit_key,
    min(coalesce(views.visit_started_at, views.session_started_at)) AS started_at,
    coalesce(sum(views.tracked_duration_ms), 0) AS tracked_ms
FROM (
    SELECT
        l.id AS lesson_id,
        l.title AS lesson_title,
        l.kind AS lesson_kind,
        s.id AS slide_id,
        coalesce(nullif(s.title, ''), concat('Slide ', s.position + 1)) AS slide_title,
        s.page_number AS page_number,
        e.status AS enrollment_status,
        u.id AS student_id,
        coalesce(nullif(u.full_name, ''), u.email) AS student_name,
        coalesce(sp.student_code, '') AS student_code,
        v.started_at AS visit_started_at,
        ls.started_at AS session_started_at,
        coalesce(v.id::text, 'session:' || ls.id::text) AS visit_key,
        cv.tracked_duration_ms
    FROM content_views cv
    JOIN learning_sessions ls ON ls.id = cv.session_id
    JOIN lessons l ON l.id = ls.lesson_id
    LEFT JOIN slides s ON s.id = cv.slide_id
    JOIN enrollments e ON e.id = ls.enrollment_id
    JOIN users u ON u.id = e.student_id
    LEFT JOIN student_profiles sp ON sp.user_id = u.id
    LEFT JOIN course_visits v ON v.id = ls.course_visit_id
    WHERE e.course_id = :'core_course_id'::uuid
      AND e.status <> 'dropped'
) AS views
GROUP BY GROUPING SETS (
    (views.lesson_id, views.lesson_title, views.lesson_kind),
    (views.slide_id, views.slide_title, views.page_number,
     views.lesson_id, views.lesson_title),
    (views.student_id, views.student_name, views.student_code,
     views.enrollment_status),
    (views.visit_key, views.student_id, views.student_name)
);

-- (3) Tổng ms/samples + distinct count theo từng nhãn AOI.
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS)
SELECT
    grouping(views.lesson_id) AS g_lesson,
    grouping(views.slide_id) AS g_slide,
    grouping(views.student_id) AS g_student,
    grouping(views.visit_key) AS g_visit,
    kv.key AS label,
    views.lesson_id,
    views.slide_id,
    views.student_id,
    views.visit_key,
    coalesce(sum(CAST(kv.value ->> 'ms' AS bigint)), 0) AS duration_ms,
    coalesce(sum(CAST(kv.value ->> 'samples' AS integer)), 0) AS sample_count,
    count(DISTINCT views.student_id) AS student_count,
    count(DISTINCT views.slide_id) AS slide_count
FROM (
    SELECT
        cv.id AS view_id,
        l.id AS lesson_id,
        s.id AS slide_id,
        u.id AS student_id,
        coalesce(v.id::text, 'session:' || ls.id::text) AS visit_key,
        cv.aoi_stats
    FROM content_views cv
    JOIN learning_sessions ls ON ls.id = cv.session_id
    JOIN lessons l ON l.id = ls.lesson_id
    LEFT JOIN slides s ON s.id = cv.slide_id
    JOIN enrollments e ON e.id = ls.enrollment_id
    JOIN users u ON u.id = e.student_id
    LEFT JOIN course_visits v ON v.id = ls.course_visit_id
    WHERE e.course_id = :'core_course_id'::uuid
      AND e.status <> 'dropped'
) AS views
JOIN jsonb_each(views.aoi_stats) AS kv ON true
WHERE jsonb_typeof(kv.value) = 'object'
  AND (CAST(kv.value ->> 'ms' AS bigint) <> 0
       OR CAST(kv.value ->> 'samples' AS integer) <> 0)
GROUP BY GROUPING SETS (
    kv.key,
    (views.lesson_id, kv.key),
    (views.slide_id, kv.key),
    (views.student_id, kv.key),
    (views.visit_key, kv.key)
);
