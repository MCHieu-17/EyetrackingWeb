-- BM25/FTS retrieval trong một course.
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS)
SELECT d.slide_id, d.course_id, d.lesson_id, d.transcript,
       ts_rank_cd(d.content_tsv, q) AS rank_score
FROM v_chatbot_slide_documents d,
     plainto_tsquery('simple', immutable_unaccent('machine learning embedding')) q
WHERE d.course_id = :'core_course_id'::uuid
  AND d.content_tsv @@ q
ORDER BY rank_score DESC
LIMIT 20;
