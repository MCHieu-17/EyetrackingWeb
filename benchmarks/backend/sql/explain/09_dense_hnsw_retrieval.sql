-- Dense pgvector/HNSW retrieval: query thẳng slides, threshold lọc sau LIMIT.
-- Lấy một vector thật từ core course làm query.
SELECT s.embedding AS query_vector
FROM slides s
JOIN lessons l ON l.id = s.lesson_id
JOIN course_modules m ON m.id = l.module_id
WHERE m.course_id = :'core_course_id'::uuid
  AND s.embedding IS NOT NULL
LIMIT 1 \gset

-- pgvector đăng ký GUC hnsw.* sau khi kiểu vector được dùng lần đầu.
SELECT NULL::vector IS NULL;
SET hnsw.ef_search = 40;
SET hnsw.iterative_scan = 'relaxed_order';

EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS)
SELECT
    s.id,
    s.lesson_id,
    1 - (s.embedding <=> :'query_vector'::vector) AS cosine
FROM slides s
WHERE s.embedding IS NOT NULL
  AND s.lesson_id = ANY(
      ARRAY(
          SELECT DISTINCT lesson_id
          FROM v_chatbot_slide_documents
          WHERE course_id = :'core_course_id'::uuid
      )
  )
  AND s.index_status = 'ready'
ORDER BY s.embedding <=> :'query_vector'::vector
LIMIT 20;
