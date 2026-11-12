"""Ingest slide version: render ảnh -> VLM mô tả -> embedding -> slide_documents.

Chỉ ingest nội dung published qua `v_published_course_outline`. Embedding text
chỉ chứa transcript của slide version bất biến; title/chương/order được lấy từ
membership khi retrieval, nên reorder không phải re-embed.
"""

import base64
import logging
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed

import openai
import psycopg
import pymupdf
from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from pgvector import Vector
from psycopg_pool import PoolTimeout
from pydantic import BaseModel, Field

from app.db import DatabaseUnavailableError, get_pool
from app.services.storage import FileStorage
from app.settings import embedding_dim, embedding_name, neu_base_url
from app.workflow.prompts import SLIDE_VLM_PROMPT
from app.workflow.providers import get_embedding, get_vlm

logger = logging.getLogger(__name__)


class VLMUnavailableError(RuntimeError):
    """Không gọi được VLM (NEU server): mất mạng, timeout hoặc lỗi tạm thời 5xx/429."""


class VLMOutput(BaseModel):
    transcript: str = Field(
        description=(
            "Faithful Markdown transcription of the slide in reading order. "
            "Preserve original text and table relationships; repeat merged-cell "
            "labels on applicable rows. Include visual descriptions separately "
            'under "Mô tả hình".'
        )
    )


def _error_text(exc: Exception) -> str:
    """Lỗi có message rỗng (vd TimeoutError) vẫn phải hiển thị dễ hiểu."""
    text = str(exc).strip()
    if text:
        return text[:500]
    if isinstance(exc, TimeoutError):
        return "Hết thời gian chờ embedding. Hệ thống sẽ thử lại."
    return type(exc).__name__


class Ingestion:
    PREFETCH = 4
    MAX_WORKERS = 4
    PDF_RENDER_DPI = 150
    PDF_CACHE_SIZE = 3

    SLIDE_QUERY = """
        SELECT
            o.slide_version_id,
            o.course_id,
            o.course_version_id,
            o.lesson_id,
            o.lesson_version_id,
            o.slide_id,
            o.slide_title,
            o.slide_position,
            o.module_title,
            o.lesson_title,
            o.pdf_asset_id,
            o.pdf_object_key,
            o.pdf_storage_backend,
            o.pdf_mime_type,
            o.source_page
        FROM v_published_course_outline o
    """

    # Dùng khi index bản nháp trước khi xuất bản. View v_course_outline chứa
    # cả draft lẫn published; retrieval vẫn chỉ đọc v_published_course_outline
    # nên slide nháp chưa xuất hiện với sinh viên.
    DRAFT_SLIDE_QUERY = """
        SELECT
            o.slide_version_id,
            o.course_id,
            o.course_version_id,
            o.lesson_id,
            o.lesson_version_id,
            o.slide_id,
            o.slide_title,
            o.slide_position,
            o.module_title,
            o.lesson_title,
            o.pdf_asset_id,
            o.pdf_object_key,
            o.pdf_storage_backend,
            o.pdf_mime_type,
            o.source_page
        FROM v_course_outline o
    """

    def __init__(self):
        vlm = get_vlm()
        self.slide_to_text_chain = self._create_chat_messages() | vlm.with_structured_output(
            VLMOutput, method="function_calling"
        )
        self.embedding = get_embedding(embedding_name())
        self.storage = FileStorage()
        self._pool = None
        self._embed_lock = threading.Lock()
        self._pdf_lock = threading.Lock()
        self._pdf_cache: OrderedDict[str, bytes] = OrderedDict()
        try:
            self._verify_vector_dim()
        except (PoolTimeout, psycopg.Error) as exc:
            raise DatabaseUnavailableError(
                "Không kết nối được PostgreSQL cho chatbot. Kiểm tra "
                "CHATBOT_DATABASE_URL và role CHATBOT_DB_USER/"
                "CHATBOT_DB_PASSWORD (role phải được tạo bởi migration). "
                f"Chi tiết: {exc}"
            ) from exc

    def _connection(self):
        return (self._pool or get_pool()).connection()

    def _verify_vector_dim(self) -> None:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT a.atttypmod
                    FROM pg_attribute a
                    WHERE a.attrelid = to_regclass('slide_documents')
                      AND a.attname = 'embedding'
                    """
                )
                row = cur.fetchone()
        if row is None:
            raise RuntimeError(
                "Không tìm thấy cột slide_documents.embedding — hãy chạy baseline mới."
            )
        column_dim = int(row["atttypmod"])
        if column_dim != embedding_dim():
            raise RuntimeError(
                f"EMBEDDING_DIM={embedding_dim()} không khớp VECTOR({column_dim}) của "
                "slide_documents.embedding."
            )
        logger.info("Embedding dimension khớp DB: vector(%s)", column_dim)

    @staticmethod
    def _dedupe(slides: list[dict]) -> list[dict]:
        seen: set[object] = set()
        unique: list[dict] = []
        for slide in slides:
            slide_version_id = slide["slide_version_id"]
            if slide_version_id in seen:
                continue
            seen.add(slide_version_id)
            unique.append(slide)
        return unique

    def _load_slide(
        self, slide_version_id: str, include_draft: bool = False
    ) -> dict | None:
        query = self.DRAFT_SLIDE_QUERY if include_draft else self.SLIDE_QUERY
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query
                    + " WHERE o.slide_version_id IS NOT NULL"
                    + " AND o.slide_version_id = %s",
                    (slide_version_id,),
                )
                return cur.fetchone()

    def _load_slides_for_lesson_version(
        self, lesson_version_id: str, include_draft: bool = False
    ) -> list[dict]:
        query = self.DRAFT_SLIDE_QUERY if include_draft else self.SLIDE_QUERY
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query
                    + " WHERE o.slide_version_id IS NOT NULL"
                    + " AND o.lesson_version_id = %s ORDER BY o.slide_position",
                    (lesson_version_id,),
                )
                return self._dedupe(list(cur.fetchall()))

    def _load_slides_for_course_version(
        self, course_version_id: str, include_draft: bool = False
    ) -> list[dict]:
        query = self.DRAFT_SLIDE_QUERY if include_draft else self.SLIDE_QUERY
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query
                    + " WHERE o.slide_version_id IS NOT NULL"
                    + " AND o.course_version_id = %s"
                    + " ORDER BY o.module_position, o.item_position, o.slide_position",
                    (course_version_id,),
                )
                return self._dedupe(list(cur.fetchall()))

    def _ready_ids(self, slide_version_ids: list[str]) -> set[str]:
        """Các slide đã ready tại thời điểm job thực sự chạy.

        Backend có thể tính danh sách target trước khi một job khác ingest
        xong; bỏ qua slide đã ready tránh ingest lại và tránh ghi đè kết quả.
        """
        if not slide_version_ids:
            return set()
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT slide_version_id
                    FROM slide_documents
                    WHERE slide_version_id = ANY(%s::uuid[])
                      AND ingestion_state = 'ready'
                    """,
                    (slide_version_ids,),
                )
                return {str(row["slide_version_id"]) for row in cur.fetchall()}

    def _load_pending_slides(self) -> list[dict]:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    self.SLIDE_QUERY
                    + """
                    LEFT JOIN slide_documents sd
                           ON sd.slide_version_id = o.slide_version_id
                    WHERE o.slide_version_id IS NOT NULL
                      AND (sd.slide_version_id IS NULL
                           OR sd.ingestion_state <> 'ready')
                    ORDER BY o.course_version_id, o.module_position,
                             o.item_position, o.slide_position
                    """
                )
                return list(cur.fetchall())

    def _create_chat_messages(self):
        return ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=SLIDE_VLM_PROMPT),
                (
                    "human",
                    [
                        {"type": "text", "text": "Chuyển slide sau thành text."},
                        {
                            "type": "image_url",
                            "image_url": {"url": "data:image/png;base64,{b64}"},
                        },
                    ],
                ),
            ]
        )

    def _pdf_bytes(self, key: str) -> bytes:
        with self._pdf_lock:
            cached = self._pdf_cache.get(key)
            if cached is not None:
                self._pdf_cache.move_to_end(key)
                return cached
        data = self.storage.load(key)
        with self._pdf_lock:
            self._pdf_cache[key] = data
            self._pdf_cache.move_to_end(key)
            while len(self._pdf_cache) > self.PDF_CACHE_SIZE:
                self._pdf_cache.popitem(last=False)
        return data

    def _load_image(self, slide: dict) -> str:
        key = slide["pdf_object_key"]
        page_no = int(slide["source_page"])
        pdf_bytes = self._pdf_bytes(key)
        with pymupdf.open(stream=pdf_bytes) as doc:
            if page_no < 1 or page_no > doc.page_count:
                raise ValueError(
                    f"Trang {page_no} nằm ngoài PDF {doc.page_count} trang"
                )
            page = doc[page_no - 1]
            pix = page.get_pixmap(dpi=self.PDF_RENDER_DPI, alpha=False)
            return base64.b64encode(pix.tobytes("png")).decode("ascii")

    def _describe_image(self, b64: str) -> str:
        try:
            from app.workflow.workload import ingest_slot

            with ingest_slot():
                return self.slide_to_text_chain.invoke({"b64": b64}).transcript
        except openai.APITimeoutError as exc:
            raise VLMUnavailableError("VLM (NEU server) không phản hồi kịp thời gian.") from exc
        except openai.APIConnectionError as exc:
            base = neu_base_url()
            raise VLMUnavailableError(
                f"Không kết nối được VLM (NEU server) tại {base}. Kiểm tra mạng và NEU_BASE_URL."
            ) from exc
        except openai.APIStatusError as exc:
            if exc.status_code == 429 or exc.status_code >= 500:
                raise VLMUnavailableError(
                    f"VLM (NEU server) tạm thời không khả dụng (HTTP {exc.status_code})."
                ) from exc
            raise

    def _mark(self, slide_version_id: str, status: str, error: str | None = None) -> None:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO slide_documents (
                        slide_version_id, pipeline_version, model_version,
                        transcript, embedding, ingestion_state, ingestion_error,
                        updated_at
                    )
                    VALUES (%s, 'rag-v2', 'qwen3-embedding-0.6b', '', NULL, %s, %s, now())
                    ON CONFLICT (slide_version_id)
                    DO UPDATE SET
                        ingestion_state = EXCLUDED.ingestion_state,
                        ingestion_error = EXCLUDED.ingestion_error,
                        updated_at = now()
                    """,
                    (slide_version_id, status, error),
                )

    def _upsert(self, slide: dict, transcript: str, vector: list[float]) -> None:
        with self._connection() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO slide_documents (
                        slide_version_id, pipeline_version, model_version,
                        transcript, embedding, ingestion_state, ingestion_error,
                        updated_at
                    )
                    VALUES (%s, 'rag-v2', 'qwen3-embedding-0.6b', %s, %s, 'ready', NULL, now())
                    ON CONFLICT (slide_version_id)
                    DO UPDATE SET
                        pipeline_version = EXCLUDED.pipeline_version,
                        model_version = EXCLUDED.model_version,
                        transcript = EXCLUDED.transcript,
                        embedding = EXCLUDED.embedding,
                        ingestion_state = 'ready',
                        ingestion_error = NULL,
                        updated_at = now()
                    """,
                    (slide["slide_version_id"], transcript, Vector(vector)),
                )

    def _embed_slide(self, slide: dict) -> None:
        slide_version_id = slide["slide_version_id"]
        self._mark(slide_version_id, "pending")
        try:
            b64 = self._load_image(slide)
            transcript = self._describe_image(b64)
            with self._embed_lock:
                vector = self.embedding.embed_documents([transcript])[0]
            self._upsert(slide, transcript, vector)
        except VLMUnavailableError as exc:
            self._mark(slide_version_id, "failed", _error_text(exc))
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Bỏ qua slide version %s do lỗi xử lý", slide_version_id)
            self._mark(slide_version_id, "failed", _error_text(exc))
            raise

    def _process_slides(self, slides: list[dict]) -> tuple[int, int, list[str]]:
        processed = 0
        failed = 0
        errors: list[str] = []
        vlm_down = 0

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as pool:
            futures = {pool.submit(self._embed_slide, slide): slide for slide in slides}
            for future in as_completed(futures):
                slide = futures[future]
                try:
                    future.result()
                    processed += 1
                except VLMUnavailableError as exc:
                    failed += 1
                    vlm_down += 1
                    errors.append(f"{slide['slide_version_id']}: {_error_text(exc)}")
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    errors.append(f"{slide['slide_version_id']}: {_error_text(exc)}")

        if vlm_down:
            raise VLMUnavailableError(
                "VLM (NEU server) tạm thời không khả dụng cho một hoặc nhiều slide."
            )
        return processed, failed, errors

    def embed_slide(
        self, slide_version_id: str, include_draft: bool = False
    ) -> tuple[int, int, list[str]]:
        slide = self._load_slide(slide_version_id, include_draft)
        if slide is None:
            raise LookupError(slide_version_id)
        return self._process_slides([slide])

    def embed_lesson_version(
        self,
        lesson_version_id: str,
        include_draft: bool = False,
        slide_version_ids: list[str] | None = None,
    ) -> tuple[int, int, list[str]]:
        slides = self._load_slides_for_lesson_version(
            lesson_version_id, include_draft
        )
        if not slides:
            raise LookupError(lesson_version_id)
        if slide_version_ids is not None:
            wanted = set(slide_version_ids)
            slides = [
                slide
                for slide in slides
                if str(slide["slide_version_id"]) in wanted
            ]
            if not slides:
                raise LookupError(lesson_version_id)
            ready = self._ready_ids(
                [str(slide["slide_version_id"]) for slide in slides]
            )
            slides = [
                slide
                for slide in slides
                if str(slide["slide_version_id"]) not in ready
            ]
            if not slides:
                return 0, 0, []
        return self._process_slides(slides)

    def embed_course_version(
        self,
        course_version_id: str,
        include_draft: bool = False,
        slide_version_ids: list[str] | None = None,
    ) -> tuple[int, int, list[str]]:
        slides = self._load_slides_for_course_version(
            course_version_id, include_draft
        )
        if not slides:
            raise LookupError(course_version_id)
        if slide_version_ids is not None:
            wanted = set(slide_version_ids)
            slides = [
                slide
                for slide in slides
                if str(slide["slide_version_id"]) in wanted
            ]
            if not slides:
                raise LookupError(course_version_id)
            ready = self._ready_ids(
                [str(slide["slide_version_id"]) for slide in slides]
            )
            slides = [
                slide
                for slide in slides
                if str(slide["slide_version_id"]) not in ready
            ]
            if not slides:
                return 0, 0, []
        return self._process_slides(slides)

    def reindex_all(self) -> tuple[int, int, list[str]]:
        slides = self._load_pending_slides()
        if not slides:
            return 0, 0, []
        return self._process_slides(slides)

    def close(self) -> None:
        self.storage.close()
