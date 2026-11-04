"""Truy hồi hybrid (pgvector + Postgres FTS) trong đúng một môn học.

Luồng:
1. Nhúng câu hỏi thành vector (Qwen3-Embedding-0.6B).
2. Chạy 2 nhánh trong cùng một SQL:
   - vector: cosine top `RAG_CANDIDATES`, lọc `course_id` + ngưỡng điểm;
   - keyword: `ts_rank_cd` trên `content_tsv` (đã unaccent + đ→d).
3. Fuse bằng Reciprocal Rank Fusion (RRF):
       score = 1/(k + vec_rank) + 1/(k + kw_rank)
4. Trả top `RAG_TOP_K` kèm metadata để dựng citation.

Phạm vi truy hồi **chỉ trong một course** theo yêu cầu: không fallback sang
course khác, không ưu tiên lesson (lesson_id chỉ dùng trong prompt).
"""

import threading

from pgvector import Vector
from psycopg.rows import dict_row

from app.db import get_pool
from app.settings import (
    rag_candidates,
    rag_rrf_k,
    rag_score_threshold,
    rag_top_k,
)
from app.workflow.providers import get_embedding

# 13 tham số theo thứ tự:
#  1 vector (vec rank)      2 vector (vec cosine)   3 course_id
#  4 vector (vec threshold) 5 threshold             6 vector (vec order)
#  7 candidates             8 query                 9 course_id
# 10 candidates            11 rrf_k                12 rrf_k
# 13 top_k
SEARCH_SQL = """
WITH vec AS (
    SELECT
        e.lesson_content_id,
        row_number() OVER (ORDER BY e.embedding <=> %s) AS rank,
        1 - (e.embedding <=> %s) AS cosine
    FROM lesson_content_embedding e
    JOIN courses c ON c.id = e.course_id
    WHERE e.course_id = %s
      AND c.deleted_at IS NULL
      AND 1 - (e.embedding <=> %s) >= %s
    ORDER BY e.embedding <=> %s
    LIMIT %s
),
kw AS (
    SELECT
        e.lesson_content_id,
        row_number() OVER (
            ORDER BY ts_rank_cd(e.content_tsv, q) DESC
        ) AS rank,
        ts_rank_cd(e.content_tsv, q) AS rank_score
    FROM lesson_content_embedding e
    JOIN courses c ON c.id = e.course_id,
         plainto_tsquery('simple', immutable_unaccent(%s)) q
    WHERE e.course_id = %s
      AND c.deleted_at IS NULL
      AND e.content_tsv @@ q
    ORDER BY ts_rank_cd(e.content_tsv, q) DESC
    LIMIT %s
)
SELECT
    e.lesson_content_id AS id,
    e.course_id,
    e.lesson_id,
    e.content,
    e.metadata,
    c.title AS course_title,
    m.title AS module_title,
    l.title AS lesson_title,
    lc.image_url,
    lc.order_index AS slide_index,
    COALESCE(1.0 / (%s + vec.rank), 0)
        + COALESCE(1.0 / (%s + kw.rank), 0) AS score,
    vec.cosine,
    kw.rank_score
FROM lesson_content_embedding e
JOIN lesson_contents lc ON lc.id = e.lesson_content_id
JOIN lessons l ON l.id = e.lesson_id
JOIN modules m ON m.id = l.module_id
JOIN courses c ON c.id = e.course_id
LEFT JOIN vec ON vec.lesson_content_id = e.lesson_content_id
LEFT JOIN kw ON kw.lesson_content_id = e.lesson_content_id
WHERE (vec.lesson_content_id IS NOT NULL OR kw.lesson_content_id IS NOT NULL)
ORDER BY score DESC
LIMIT %s
"""


class Retriever:
    """Truy hồi slide theo câu hỏi trong phạm vi một course."""

    def __init__(self):
        self.embedding = get_embedding()
        self.top_k = rag_top_k()
        self.candidates = rag_candidates()
        self.rrf_k = rag_rrf_k()
        self.threshold = rag_score_threshold()

    def _query(self, vector: Vector, query: str, course_id: str) -> list[dict]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    SEARCH_SQL,
                    (
                        vector,          # 1 vec rank
                        vector,          # 2 vec cosine
                        course_id,       # 3
                        vector,          # 4 vec threshold
                        self.threshold,  # 5
                        vector,          # 6 vec order
                        self.candidates, # 7
                        query,           # 8 kw query
                        course_id,       # 9
                        self.candidates, # 10
                        self.rrf_k,      # 11
                        self.rrf_k,      # 12
                        self.top_k,      # 13
                    ),
                )
                return [dict(row) for row in cur.fetchall()]

    def search(self, query: str, course_id: str) -> list[dict]:
        """Trả về các slide liên quan nhất trong đúng course."""
        vector = Vector(self.embedding.embed_query(query))
        return self._query(vector, query, course_id)

    async def asearch(self, query: str, course_id: str) -> list[dict]:
        import asyncio
        vector = Vector(await self.embedding.aembed_query(query))
        return await asyncio.to_thread(self._query, vector, query, course_id)

    def close(self):
        # `self.embedding` là client dùng chung (lru_cache registry) -> KHÔNG đóng.
        return


# Singleton: dùng chung 1 retriever trong toàn bộ tiến trình
_retriever: Retriever | None = None
_retriever_lock = threading.Lock()


def get_retriever() -> Retriever:
    """Lazy singleton (connection mượn từ pool dùng chung)."""
    global _retriever
    if _retriever is None:
        with _retriever_lock:
            if _retriever is None:
                _retriever = Retriever()
    return _retriever


def close_retriever() -> None:
    global _retriever
    if _retriever is not None:
        _retriever.close()
        _retriever = None


def build_citations(docs: list[dict]) -> list[dict]:
    """Dựng citation trong code (không tin LLM tự bịa nguồn)."""
    citations: list[dict] = []
    for doc in docs:
        content = doc.get("content") or ""
        citations.append(
            {
                "document_id": str(doc["id"]),
                "title": f"{doc['module_title']} - {doc['lesson_title']}",
                "location": doc.get("image_url") or "",
                "lesson_id": str(doc["lesson_id"]) if doc.get("lesson_id") else None,
                "lesson_title": doc.get("lesson_title") or "",
                "slide_id": str(doc["id"]),
                "slide_index": doc.get("slide_index"),
                "image_url": doc.get("image_url") or "",
                "snippet": content[:300],
                "score": float(doc.get("score") or 0.0),
            }
        )
    return citations


def format_context(docs: list[dict]) -> str:
    """Đánh số tài liệu [1], [2]... để LLM tham chiếu khi trả lời."""
    blocks: list[str] = []
    for index, doc in enumerate(docs, start=1):
        header = (
            f"[{index}] {doc['course_title']} > "
            f"{doc['module_title']} > {doc['lesson_title']} "
            f"(slide {doc.get('slide_index')})"
        )
        blocks.append(f"{header}\n{doc.get('content') or ''}")
    return "\n\n".join(blocks)
