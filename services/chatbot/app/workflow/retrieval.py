"""Truy hồi hybrid (pgvector + Postgres FTS) trong đúng course version.

Cả vector và keyword đều lọc `course_id` + `course_version_id` **trước LIMIT**.
Không đưa title/chương/order mutable vào embedding text; metadata citation lấy
từ membership published tại thời điểm truy hồi.
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

SEARCH_SQL = """
WITH vec AS (
    SELECT
        d.slide_version_id,
        row_number() OVER (ORDER BY d.embedding <=> %s) AS rank,
        1 - (d.embedding <=> %s) AS cosine
    FROM v_chatbot_slide_documents d
    WHERE d.course_id = %s
      AND d.course_version_id = %s
      AND 1 - (d.embedding <=> %s) >= %s
    ORDER BY d.embedding <=> %s
    LIMIT %s
),
kw AS (
    SELECT
        d.slide_version_id,
        row_number() OVER (
            ORDER BY ts_rank_cd(d.content_tsv, q) DESC
        ) AS rank,
        ts_rank_cd(d.content_tsv, q) AS rank_score
    FROM v_chatbot_slide_documents d,
         plainto_tsquery('simple', immutable_unaccent(%s)) q
    WHERE d.course_id = %s
      AND d.course_version_id = %s
      AND d.content_tsv @@ q
    ORDER BY ts_rank_cd(d.content_tsv, q) DESC
    LIMIT %s
)
SELECT
    d.slide_version_id AS id,
    d.course_id,
    d.course_version_id,
    d.lesson_id,
    d.lesson_version_id,
    d.lesson_version_slide_id AS membership_id,
    d.slide_id,
    d.pdf_asset_id AS asset_id,
    d.pdf_object_key,
    d.pdf_storage_backend,
    d.pdf_mime_type,
    d.source_page,
    d.transcript AS content,
    d.slide_title,
    d.module_title,
    d.lesson_title,
    d.slide_position AS slide_index,
    COALESCE(1.0 / (%s + vec.rank), 0)
        + COALESCE(1.0 / (%s + kw.rank), 0) AS score,
    vec.cosine,
    kw.rank_score
FROM v_chatbot_slide_documents d
LEFT JOIN vec ON vec.slide_version_id = d.slide_version_id
LEFT JOIN kw ON kw.slide_version_id = d.slide_version_id
WHERE (vec.slide_version_id IS NOT NULL OR kw.slide_version_id IS NOT NULL)
ORDER BY score DESC
LIMIT %s
"""


class Retriever:
    def __init__(self):
        self.embedding = get_embedding()
        self.top_k = rag_top_k()
        self.candidates = rag_candidates()
        self.rrf_k = rag_rrf_k()
        self.threshold = rag_score_threshold()

    def _query(
        self, vector: Vector, query: str, course_id: str, course_version_id: str
    ) -> list[dict]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    SEARCH_SQL,
                    (
                        vector,
                        vector,
                        course_id,
                        course_version_id,
                        vector,
                        self.threshold,
                        vector,
                        self.candidates,
                        query,
                        course_id,
                        course_version_id,
                        self.candidates,
                        self.rrf_k,
                        self.rrf_k,
                        self.top_k,
                    ),
                )
                return [dict(row) for row in cur.fetchall()]

    async def asearch(
        self, query: str, course_id: str, course_version_id: str
    ) -> list[dict]:
        import asyncio

        vector = Vector(await self.embedding.aembed_query(query))
        return await asyncio.to_thread(
            self._query, vector, query, course_id, course_version_id
        )

    def close(self):
        return


_retriever: Retriever | None = None
_retriever_lock = threading.Lock()


def get_retriever() -> Retriever:
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
    citations: list[dict] = []
    for doc in docs:
        content = doc.get("content") or ""
        asset_id = doc.get("asset_id")
        page_number = doc.get("source_page")
        pdf_url = f"/media/assets/{asset_id}/file" if asset_id else ""
        location = doc.get("pdf_object_key") or ""
        if location and page_number:
            location = f"{location}#page={page_number}"
        citations.append(
            {
                "document_id": str(doc["id"]),
                "course_version_id": str(doc["course_version_id"])
                if doc.get("course_version_id")
                else None,
                "lesson_version_id": str(doc["lesson_version_id"])
                if doc.get("lesson_version_id")
                else None,
                "slide_version_id": str(doc["id"]),
                "membership_id": str(doc["membership_id"])
                if doc.get("membership_id")
                else None,
                "asset_id": str(asset_id) if asset_id else None,
                "title": f"{doc['module_title']} - {doc['lesson_title']}",
                "location": location,
                "lesson_id": str(doc["lesson_id"]) if doc.get("lesson_id") else None,
                "lesson_title": doc.get("lesson_title") or "",
                "slide_id": str(doc["slide_id"]) if doc.get("slide_id") else None,
                "slide_index": doc.get("slide_index"),
                "pdf_url": pdf_url,
                "page_number": page_number,
                "snippet": content[:300],
                "score": float(doc.get("score") or 0.0),
            }
        )
    return citations


def format_context(docs: list[dict]) -> str:
    blocks: list[str] = []
    for index, doc in enumerate(docs, start=1):
        header = (
            f"[{index}] {doc['module_title']} > "
            f"{doc['lesson_title']} "
            f"(slide {doc.get('slide_index')})"
        )
        blocks.append(f"{header}\n{doc.get('content') or ''}")
    return "\n\n".join(blocks)
