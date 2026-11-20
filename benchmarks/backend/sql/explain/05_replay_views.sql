-- Replay: view ids + sample stats (khớp query group-by trong replay.py).
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS)
WITH view_ids AS (
    SELECT cv.id
    FROM content_views cv
    JOIN learning_sessions ls ON ls.id = cv.session_id
    WHERE ls.course_visit_id = :'core_visit_id'::uuid
)
SELECT
    cv.id,
    ls.started_at,
    cv.sequence_no,
    s.id AS slide_id,
    st.first_sample,
    st.last_sample,
    st.sample_count
FROM content_views cv
JOIN learning_sessions ls ON ls.id = cv.session_id
LEFT JOIN slides s ON s.id = cv.slide_id
LEFT JOIN (
    SELECT
        gs.content_view_id,
        min(gs.event_time) AS first_sample,
        max(gs.event_time) AS last_sample,
        count(*) AS sample_count
    FROM gaze_samples gs
    WHERE gs.content_view_id IN (SELECT id FROM view_ids)
    GROUP BY gs.content_view_id
) st ON st.content_view_id = cv.id
WHERE cv.id IN (SELECT id FROM view_ids)
ORDER BY ls.started_at, cv.sequence_no;
