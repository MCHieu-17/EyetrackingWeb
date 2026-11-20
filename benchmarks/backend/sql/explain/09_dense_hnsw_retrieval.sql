-- Dense pgvector/HNSW retrieval. Lấy một vector thật từ core course làm query.
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS)
WITH q AS (
    SELECT embedding
    FROM slides s
    JOIN lessons l ON l.id = s.lesson_id
    JOIN course_modules m ON m.id = l.module_id
    WHERE m.course_id = :'core_course_id'::uuid
      AND s.embedding IS NOT NULL
    LIMIT 1
)
SELECT d.slide_id, d.course_id, d.lesson_id, d.transcript,
       1 - (d.embedding <=> q.embedding) AS cosine
FROM v_chatbot_slide_documents d, q
WHERE d.course_id = :'core_course_id'::uuid
ORDER BY d.embedding <=> q.embedding
LIMIT 20;
