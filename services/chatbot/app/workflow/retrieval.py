"""Truy hồi hybrid: BM25-like (Postgres FTS) + dense (pgvector) + HyDE.

Mỗi nhánh lọc `course_id` + `course_version_id` **trước LIMIT**. Các nhánh được
fuse bằng Reciprocal Rank Fusion (RRF) trong Python để dễ test và tune trọng số.

BM25 ở đây dùng Postgres FTS `ts_rank_cd` (không phải BM25 chuẩn) vì stack hiện
tại không có extension BM25. Nếu sau này cần BM25 thật, chỉ cần thay
`_search_bm25` mà không đổi pipeline.
"""

import asyncio
import threading

from pgvector import Vector
from psycopg.rows import dict_row

from app.db import get_pool
from app.settings import (
    rag_bm25_candidates,
    rag_dense_candidates,
    rag_hyde_candidates,
    rag_hyde_weight,
    rag_rrf_k,
    rag_score_threshold,
    rag_top_k,
)
from app.workflow.providers import get_embedding

_DOC_COLUMNS = """
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
    d.slide_position AS slide_index
"""

BM25_SQL = f"""
SELECT
    {_DOC_COLUMNS},
    ts_rank_cd(d.content_tsv, q) AS rank_score
FROM v_chatbot_slide_documents d,
     plainto_tsquery('simple', immutable_unaccent(%s)) q
WHERE d.course_id = %s
  AND d.course_version_id = %s
  AND d.content_tsv @@ q
ORDER BY rank_score DESC
LIMIT %s
"""

DENSE_SQL = f"""
SELECT
    {_DOC_COLUMNS},
    1 - (d.embedding <=> %s) AS cosine
FROM v_chatbot_slide_documents d
WHERE d.course_id = %s
  AND d.course_version_id = %s
  AND 1 - (d.embedding <=> %s) >= %s
ORDER BY d.embedding <=> %s
LIMIT %s
"""


def rrf_fuse(
    branches: list[tuple[list[dict], float]], k: int, top_k: int
) -> list[dict]:
    """Fuse nhiều ranked lists bằng RRF.

    `branches` là danh sách (docs, weight). Mỗi docs đã được xếp hạng từ 1.
    """
    scores: dict[str, float] = {}
    docs: dict[str, dict] = {}
    for branch, weight in branches:
        for rank, doc in enumerate(branch, start=1):
            key = str(doc["id"])
            docs.setdefault(key, doc)
            scores[key] = scores.get(key, 0.0) + weight / (k + rank)

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]
    result: list[dict] = []
    for key, score in ordered:
        doc = dict(docs[key])
        doc["score"] = score
        result.append(doc)
    return result


class Retriever:
    def __init__(self):
        self.embedding = get_embedding()
        self.top_k = rag_top_k()
        self.bm25_candidates = rag_bm25_candidates()
        self.dense_candidates = rag_dense_candidates()
        self.hyde_candidates = rag_hyde_candidates()
        self.hyde_weight = rag_hyde_weight()
        self.rrf_k = rag_rrf_k()
        self.threshold = rag_score_threshold()

    def _search_bm25(
        self, query: str, course_id: str, course_version_id: str
    ) -> list[dict]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    BM25_SQL,
                    (query, course_id, course_version_id, self.bm25_candidates),
                )
                return [dict(row) for row in cur.fetchall()]

    def _search_dense(
        self,
        vector: Vector,
        course_id: str,
        course_version_id: str,
        limit: int,
    ) -> list[dict]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    DENSE_SQL,
                    (
                        vector,
                        course_id,
                        course_version_id,
                        vector,
                        self.threshold,
                        vector,
                        limit,
                    ),
                )
                return [dict(row) for row in cur.fetchall()]

    async def asearch(
        self,
        query: str,
        hyde: str,
        course_id: str,
        course_version_id: str,
    ) -> list[dict]:
        query_vector, hyde_vector = await asyncio.gather(
            self.embedding.aembed_query(query),
            self.embedding.aembed_query(hyde) if hyde else _none(),
        )

        tasks = [
            asyncio.to_thread(
                self._search_bm25, query, course_id, course_version_id
            ),
            asyncio.to_thread(
                self._search_dense,
                Vector(query_vector),
                course_id,
                course_version_id,
                self.dense_candidates,
            ),
        ]
        if hyde_vector is not None:
            tasks.append(
                asyncio.to_thread(
                    self._search_dense,
                    Vector(hyde_vector),
                    course_id,
                    course_version_id,
                    self.hyde_candidates,
                )
            )
        results = await asyncio.gather(*tasks)

        branches: list[tuple[list[dict], float]] = [
            (results[0], 1.0),
            (results[1], 1.0),
        ]
        if hyde_vector is not None:
            branches.append((results[2], self.hyde_weight))
        return rrf_fuse(branches, self.rrf_k, self.top_k)

    def close(self):
        return


async def _none():
    return None


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
                "snippet": content[:500],
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
