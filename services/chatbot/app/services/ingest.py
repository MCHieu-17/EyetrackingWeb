"""Ingest slide: render ảnh -> VLM mô tả -> embedding -> bảng slides.

Backend chỉ gửi danh sách slide ID. Chatbot đọc nội dung hiện hành qua
`v_course_outline` (kể cả khóa còn nháp) và cập nhật trực tiếp transcript,
embedding, index_status trên cùng row.
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
    text = str(exc).strip()
    if text:
        return text[:500]
    if isinstance(exc, TimeoutError):
        return "Hết thời gian chờ embedding. Hệ thống sẽ thử lại."
    return type(exc).__name__


class Ingestion:
    MAX_WORKERS = 4
    PDF_RENDER_DPI = 150
    PDF_CACHE_SIZE = 3

    SLIDE_QUERY = """
        SELECT
            o.slide_id,
            o.course_id,
            o.lesson_id,
            o.slide_title,
            o.slide_position,
            o.index_status,
            o.module_title,
            o.lesson_title,
            o.pdf_asset_id,
            o.pdf_object_key,
            o.pdf_storage_backend,
            o.pdf_mime_type,
            o.source_page
        FROM v_course_outline o
        WHERE o.slide_id = ANY(%(slide_ids)s::uuid[])
        ORDER BY o.module_position, o.lesson_position, o.slide_position
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
                    WHERE a.attrelid = to_regclass('slides')
                      AND a.attname = 'embedding'
                    """
                )
                row = cur.fetchone()
        if row is None:
            raise RuntimeError(
                "Không tìm thấy cột slides.embedding — hãy chạy baseline generation 13."
            )
        column_dim = int(row["atttypmod"])
        if column_dim != embedding_dim():
            raise RuntimeError(
                f"EMBEDDING_DIM={embedding_dim()} không khớp VECTOR({column_dim}) của "
                "slides.embedding."
            )
        logger.info("Embedding dimension khớp DB: vector(%s)", column_dim)

    def _load_slides(self, slide_ids: list[str]) -> list[dict]:
        if not slide_ids:
            return []
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(self.SLIDE_QUERY, {"slide_ids": slide_ids})
                return list(cur.fetchall())

    def _load_pending_slides(self) -> list[dict]:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        o.slide_id, o.course_id, o.lesson_id, o.slide_title,
                        o.slide_position, o.module_title, o.lesson_title,
                        o.pdf_asset_id, o.pdf_object_key, o.pdf_storage_backend,
                        o.pdf_mime_type, o.source_page
                    FROM v_course_outline o
                    WHERE o.slide_id IS NOT NULL AND o.index_status <> 'ready'
                    ORDER BY o.course_id, o.module_position,
                             o.lesson_position, o.slide_position
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

    def _mark(self, slide_id: str, status: str, error: str | None = None) -> None:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE slides
                    SET index_status = %s,
                        index_error = %s,
                        updated_at = now()
                    WHERE id = %s
                    """,
                    (status, error, slide_id),
                )

    def _upsert(self, slide: dict, transcript: str, vector: list[float]) -> None:
        with self._connection() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE slides
                    SET pipeline_version = 'rag-v2',
                        model_version = 'qwen3-embedding-0.6b',
                        transcript = %s,
                        embedding = %s,
                        index_status = 'ready',
                        index_error = NULL,
                        updated_at = now()
                    WHERE id = %s
                    """,
                    (transcript, Vector(vector), slide["slide_id"]),
                )

    def _embed_slide(self, slide: dict) -> None:
        slide_id = slide["slide_id"]
        self._mark(slide_id, "pending")
        try:
            b64 = self._load_image(slide)
            transcript = self._describe_image(b64)
            with self._embed_lock:
                vector = self.embedding.embed_documents([transcript])[0]
            self._upsert(slide, transcript, vector)
        except VLMUnavailableError as exc:
            self._mark(slide_id, "failed", _error_text(exc))
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Bỏ qua slide %s do lỗi xử lý", slide_id)
            self._mark(slide_id, "failed", _error_text(exc))
            raise

    def _process_slides(self, slides: list[dict]) -> tuple[int, int, list[str]]:
        processed = failed = 0
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
                    errors.append(f"{slide['slide_id']}: {_error_text(exc)}")
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    errors.append(f"{slide['slide_id']}: {_error_text(exc)}")

        # Chỉ báo lỗi transport khi không có slide nào thành công. Nếu đã có
        # slide ready, trả counts để backend giữ nguyên kết quả thành công và
        # chỉ retry các slide còn failed/pending.
        if vlm_down and processed == 0:
            raise VLMUnavailableError(
                "VLM (NEU server) tạm thời không khả dụng cho một hoặc nhiều slide."
            )
        return processed, failed, errors

    def embed_slides(self, slide_ids: list[str]) -> tuple[int, int, list[str]]:
        slides = self._load_slides(slide_ids)
        if not slides:
            raise LookupError("slides")
        # Backend có thể vừa ingest xong các slide này ở request khác. Bỏ qua
        # slide đã ready để retry/status idempotent, trừ khi backend đã đánh
        # dấu pending trước đó (reindex có chủ đích).
        slides = [
            slide for slide in slides if slide.get("index_status") != "ready"
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
