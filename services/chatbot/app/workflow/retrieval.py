"""Truy hồi hybrid: Postgres FTS + pgvector + HyDE trong một khóa học."""

import asyncio
import re
import threading

from pgvector import Vector

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
    d.slide_id AS id,
    d.course_id,
    d.lesson_id,
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

# View lọc published + ready; chỉ lấy lesson id để query thẳng slides.
COURSE_LESSONS_SQL = """
SELECT DISTINCT lesson_id
FROM v_chatbot_slide_documents
WHERE course_id = %s
"""

# Vòng 1 chỉ trả id + điểm; transcript/metadata lấy sau cho top_k.
BM25_SQL = """
SELECT
    s.id,
    ts_rank_cd(s.content_tsv, q) AS rank_score
FROM slides s,
     plainto_tsquery('simple', immutable_unaccent(%s)) q
WHERE s.lesson_id = ANY(%s::uuid[])
  AND s.content_tsv @@ q
  AND s.index_status = 'ready'
ORDER BY rank_score DESC
LIMIT %s
"""

# ORDER BY <=> LIMIT trực tiếp trên slides để planner có thể dùng HNSW.
# Threshold lọc sau LIMIT (xem _dense_rows).
DENSE_SQL = """
SELECT
    s.id,
    s.lesson_id,
    1 - (s.embedding <=> %s) AS cosine
FROM slides s
WHERE s.embedding IS NOT NULL
  AND s.lesson_id = ANY(%s::uuid[])
  AND s.index_status = 'ready'
ORDER BY s.embedding <=> %s
LIMIT %s
"""

HYDRATE_SQL = f"""
SELECT
    {_DOC_COLUMNS}
FROM v_chatbot_slide_documents d
WHERE d.course_id = %s
  AND d.slide_id = ANY(%s::uuid[])
"""

# Budget prompt: đủ rộng cho slide thường nhưng chặn transcript cực dài.
_CONTEXT_MAX_CHARS = 20_000
_DOC_MAX_CHARS = 2_500


def rrf_fuse(
    branches: list[tuple[list[dict], float]], k: int, top_k: int
) -> list[dict]:
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


def _context_header(index: int, doc: dict) -> str:
    return (
        f"[{index}] {doc['module_title']} > "
        f"{doc['lesson_title']} "
        f"(slide {int(doc.get('slide_index') or 0)})"
    )


def _clip_text(text: str, query: str, limit: int) -> str:
    """Cắt quanh token khớp đầu tiên để giữ đoạn có khả năng trả lời."""
    if len(text) <= limit:
        return text
    lowered = text.casefold()
    position = -1
    for term in re.findall(r"\w{3,}", query.casefold()):
        found = lowered.find(term)
        if found >= 0 and (position < 0 or found < position):
            position = found
    if position < 0:
        return text[:limit]
    start = max(0, min(position - limit // 3, len(text) - limit))
    return text[start : start + limit]


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
        self.ef_search = max(40, 4 * self.top_k)

    @staticmethod
    def _course_lesson_ids(conn, course_id: str) -> list:
        rows = conn.execute(COURSE_LESSONS_SQL, (course_id,)).fetchall()
        return [row["lesson_id"] for row in rows]

    def _bm25_rows(self, conn, query: str, lesson_ids: list) -> list[dict]:
        if not lesson_ids:
            return []
        rows = conn.execute(
            BM25_SQL,
            (query, lesson_ids, self.bm25_candidates),
        ).fetchall()
        return [dict(row) for row in rows]

    def _apply_retrieval_settings(self, conn) -> None:
        # Chạm kiểu vector trước để pgvector đăng ký GUC hnsw.* trong session.
        conn.execute("SELECT NULL::vector")
        conn.execute(f"SET LOCAL hnsw.ef_search = {int(self.ef_search)}")
        conn.execute("SET LOCAL hnsw.iterative_scan = 'relaxed_order'")

    def _dense_rows(self, conn, vector, lesson_ids: list, limit: int) -> list[dict]:
        if not lesson_ids:
            return []
        rows = conn.execute(
            DENSE_SQL,
            (vector, lesson_ids, vector, limit),
        ).fetchall()
        docs = [dict(row) for row in rows]
        # relaxed_order có thể lệch thứ tự; sort lại trước khi lọc threshold.
        docs.sort(key=lambda row: row["cosine"], reverse=True)
        return [row for row in docs if row["cosine"] >= self.threshold]

    def _hydrate(self, conn, course_id: str, docs: list[dict]) -> list[dict]:
        if not docs:
            return []
        ids = [doc["id"] for doc in docs]
        rows = conn.execute(HYDRATE_SQL, (course_id, ids)).fetchall()
        by_id = {str(row["id"]): dict(row) for row in rows}
        hydrated: list[dict] = []
        for doc in docs:
            full = by_id.get(str(doc["id"]))
            if full is None:
                continue
            full["score"] = doc.get("score", 0.0)
            hydrated.append(full)
        return hydrated

    def _search_bm25_and_lessons(
        self, query: str, course_id: str
    ) -> tuple[list, list[dict]]:
        with get_pool().connection() as conn:
            lesson_ids = self._course_lesson_ids(conn, course_id)
            return lesson_ids, self._bm25_rows(conn, query, lesson_ids)

    def _search_bm25(self, query: str, course_id: str) -> list[dict]:
        return self._search_bm25_and_lessons(query, course_id)[1]

    def _search_dense(self, vector: Vector, course_id: str, limit: int) -> list[dict]:
        with get_pool().connection() as conn:
            lesson_ids = self._course_lesson_ids(conn, course_id)
            if not lesson_ids:
                return []
            with conn.transaction():
                self._apply_retrieval_settings(conn)
                return self._dense_rows(conn, vector, lesson_ids, limit)

    def _dense_and_hydrate(
        self,
        query_vector: Vector,
        hyde_vector: Vector | None,
        course_id: str,
        lesson_ids: list,
        bm25: list[dict],
    ) -> list[dict]:
        with get_pool().connection() as conn:
            with conn.transaction():
                self._apply_retrieval_settings(conn)
                dense = self._dense_rows(
                    conn, query_vector, lesson_ids, self.dense_candidates
                )
                hyde = (
                    self._dense_rows(
                        conn, hyde_vector, lesson_ids, self.hyde_candidates
                    )
                    if hyde_vector is not None
                    else []
                )
                branches: list[tuple[list[dict], float]] = [
                    (bm25, 1.0),
                    (dense, 1.0),
                ]
                if hyde_vector is not None:
                    branches.append((hyde, self.hyde_weight))
                fused = rrf_fuse(branches, self.rrf_k, self.top_k)
                return self._hydrate(conn, course_id, fused)

    async def asearch(self, query: str, hyde: str, course_id: str) -> list[dict]:
        bm25_task = asyncio.create_task(
            asyncio.to_thread(self._search_bm25_and_lessons, query, course_id)
        )
        vectors_task = asyncio.gather(
            self.embedding.aembed_query(query),
            self.embedding.aembed_query(hyde) if hyde else _none(),
        )
        (lesson_ids, bm25), (query_vector, hyde_vector) = await asyncio.gather(
            bm25_task, vectors_task
        )
        if not lesson_ids:
            return []
        return await asyncio.to_thread(
            self._dense_and_hydrate,
            Vector(query_vector),
            Vector(hyde_vector) if hyde_vector is not None else None,
            course_id,
            lesson_ids,
            bm25,
        )

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
        slide_id = str(doc["id"])
        lesson_id = str(doc["lesson_id"]) if doc.get("lesson_id") else None
        citations.append(
            {
                "document_id": slide_id,
                "lesson_id": lesson_id,
                "slide_id": slide_id,
                "asset_id": str(asset_id) if asset_id else None,
                "title": f"{doc['module_title']} - {doc['lesson_title']}",
                "location": location,
                "lesson_title": doc.get("lesson_title") or "",
                "slide_index": doc.get("slide_index"),
                "pdf_url": pdf_url,
                "page_number": page_number,
                "snippet": content[:500],
                "score": float(doc.get("score") or 0.0),
            }
        )
    return citations


def format_context(docs: list[dict], query: str = "") -> str:
    unique: list[dict] = []
    seen: set[str] = set()
    for doc in docs:
        key = str(doc.get("id"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(doc)
    if not unique:
        return ""

    headers = [_context_header(index, doc) for index, doc in enumerate(unique, start=1)]
    overhead = sum(len(header) + 1 for header in headers)
    overhead += 2 * max(0, len(unique) - 1)
    body_budget = max(1, _CONTEXT_MAX_CHARS - overhead)
    per_doc = max(1, min(_DOC_MAX_CHARS, body_budget // len(unique)))

    blocks: list[str] = []
    for header, doc in zip(headers, unique, strict=True):
        body = _clip_text(doc.get("content") or "", query, per_doc)
        blocks.append(f"{header}\n{body}")
    text = "\n\n".join(blocks)
    return text[:_CONTEXT_MAX_CHARS]
