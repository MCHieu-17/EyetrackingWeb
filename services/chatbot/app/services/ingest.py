"""Ingest slide: render ảnh -> VLM mô tả -> embedding -> bảng slides.

Backend chỉ gửi danh sách slide ID. Chatbot đọc nội dung hiện hành qua
`v_course_outline` (kể cả khóa còn nháp) và cập nhật trực tiếp transcript,
embedding, index_status trên cùng row.

Pipeline trong một request: gom slide theo PDF, mở/parse PDF một lần cho mỗi
nhóm, chạy render + VLM song song theo `VLM_INGEST_CONCURRENCY`, rồi gom
transcript thành batch để embedding. Embedding chạy nền trong lúc các slide
kế tiếp đang được VLM xử lý nên không chặn toàn bộ request.
"""

import base64
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Empty, Queue

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
from app.settings import (
    embedding_dim,
    embedding_model_version,
    llm_base_url,
)
from app.workflow.prompts import SLIDE_VLM_PROMPT
from app.workflow.providers import get_embedding, get_vlm

logger = logging.getLogger(__name__)


class VLMUnavailableError(RuntimeError):
    """Không gọi được VLM: mất mạng, timeout hoặc lỗi tạm thời 5xx/429."""


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
    # Số thread render + VLM mỗi request; dùng chung biến với slot VLM để
    # không có thread nào ngồi chờ semaphore vô ích.
    MAX_WORKERS = max(1, int(os.getenv("VLM_INGEST_CONCURRENCY", "4")))
    EMBED_BATCH = 8
    # Chờ ngắn để gom thêm transcript vừa xong trong cùng wave VLM.
    EMBED_BATCH_WINDOW_SECONDS = 0.2
    PDF_RENDER_DPI = 150

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
        self.embedding = get_embedding()
        self.storage = FileStorage()
        self._pool = None
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

    def job_keys(self, slide_ids: list[str]) -> tuple[str, ...]:
        """Khoá single-flight theo lesson cho một loạt slide cần ingest."""
        if not slide_ids:
            return ("empty",)
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT lesson_id::text AS lesson_id
                    FROM slides
                    WHERE id = ANY(%s::uuid[])
                    """,
                    (slide_ids,),
                )
                rows = cur.fetchall()
        return tuple(sorted(row["lesson_id"] for row in rows)) or ("unknown",)

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

    def _open_document(self, key: str) -> tuple[pymupdf.Document, bytes]:
        """Mở PDF một lần; giữ bytes sống cùng Document trong suốt nhóm."""
        data = self.storage.load(key)
        return pymupdf.open(stream=data, filetype="pdf"), data

    def _load_image(
        self,
        slide: dict,
        document: pymupdf.Document,
        render_lock: threading.Lock,
    ) -> str:
        page_no = int(slide["source_page"])
        with render_lock:
            if page_no < 1 or page_no > document.page_count:
                raise ValueError(
                    f"Trang {page_no} nằm ngoài PDF {document.page_count} trang"
                )
            page = document[page_no - 1]
            pix = page.get_pixmap(dpi=self.PDF_RENDER_DPI, alpha=False)
            png = pix.tobytes("png")
        return base64.b64encode(png).decode("ascii")

    def _describe_image(self, b64: str) -> str:
        try:
            from app.workflow.workload import ingest_slot

            with ingest_slot():
                return self.slide_to_text_chain.invoke({"b64": b64}).transcript
        except openai.APITimeoutError as exc:
            raise VLMUnavailableError("VLM không phản hồi kịp thời gian.") from exc
        except openai.APIConnectionError as exc:
            base = llm_base_url()
            raise VLMUnavailableError(
                f"Không kết nối được VLM tại {base}. Kiểm tra mạng và LLM_BASE_URL."
            ) from exc
        except openai.APIStatusError as exc:
            if exc.status_code == 429 or exc.status_code >= 500:
                raise VLMUnavailableError(
                    f"VLM tạm thời không khả dụng (HTTP {exc.status_code})."
                ) from exc
            raise

    def _mark(self, slide_id: str, status: str, error: str | None = None) -> None:
        self._mark_many([slide_id], status, error)

    def _mark_many(
        self, slide_ids: list[str], status: str, error: str | None = None
    ) -> None:
        unique_ids = list(dict.fromkeys(slide_ids))
        if not unique_ids:
            return
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE slides
                    SET index_status = %s,
                        index_error = %s,
                        updated_at = now()
                    WHERE id = ANY(%s::uuid[])
                    """,
                    (status, error, unique_ids),
                )

    def _upsert(self, slide: dict, transcript: str, vector: list[float]) -> None:
        with self._connection() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE slides
                    SET pipeline_version = 'rag-v2',
                        model_version = %s,
                        transcript = %s,
                        embedding = %s,
                        index_status = 'ready',
                        index_error = NULL,
                        updated_at = now()
                    WHERE id = %s
                    """,
                    (
                        embedding_model_version(),
                        transcript,
                        Vector(vector),
                        slide["slide_id"],
                    ),
                )

    def _prepare_slide(
        self,
        slide: dict,
        document: pymupdf.Document,
        render_lock: threading.Lock,
    ) -> dict:
        """Render + VLM một slide; trả transcript kèm timing cho embedder."""
        render_started = time.perf_counter()
        b64 = self._load_image(slide, document, render_lock)
        render_ms = (time.perf_counter() - render_started) * 1000

        vlm_started = time.perf_counter()
        transcript = self._describe_image(b64)
        return {
            "slide": slide,
            "transcript": transcript,
            "render_ms": render_ms,
            "vlm_ms": (time.perf_counter() - vlm_started) * 1000,
        }

    @staticmethod
    def _failed(
        result: dict,
        result_lock: threading.Lock,
        slides: list[dict],
        exc: Exception,
        *,
        vlm_down: bool = False,
    ) -> None:
        with result_lock:
            result["failed"] += len(slides)
            if vlm_down:
                result["vlm_down"] += len(slides)
            for slide in slides:
                result["errors"].append(
                    f"{slide['slide_id']}: {_error_text(exc)}"
                )

    def _embed_batch(
        self,
        batch: list[dict],
        result: dict,
        result_lock: threading.Lock,
    ) -> None:
        texts = [item["transcript"] for item in batch]
        slides = [item["slide"] for item in batch]
        started = time.perf_counter()
        try:
            vectors = self.embedding.embed_documents(texts)
            if len(vectors) != len(batch):
                raise RuntimeError(
                    f"Embedding trả {len(vectors)} vector cho {len(batch)} slide"
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Embedding batch lỗi (%s slide): %s", len(batch), _error_text(exc)
            )
            self._mark_many(
                [slide["slide_id"] for slide in slides], "failed", _error_text(exc)
            )
            self._failed(result, result_lock, slides, exc)
            return
        embed_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "ingest embed batch=%s embed_ms=%.0f", len(batch), embed_ms
        )

        for item, vector in zip(batch, vectors, strict=True):
            slide = item["slide"]
            db_started = time.perf_counter()
            try:
                self._upsert(slide, item["transcript"], vector)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Upsert slide %s lỗi", slide["slide_id"])
                self._mark(slide["slide_id"], "failed", _error_text(exc))
                self._failed(result, result_lock, [slide], exc)
                continue
            db_ms = (time.perf_counter() - db_started) * 1000
            with result_lock:
                result["processed"] += 1
            logger.info(
                "ingest slide=%s render_ms=%.0f vlm_ms=%.0f embed_ms=%.0f db_ms=%.0f",
                slide["slide_id"],
                item["render_ms"],
                item["vlm_ms"],
                embed_ms / len(batch),
                db_ms,
            )

    def _process_slides(self, slides: list[dict]) -> tuple[int, int, list[str]]:
        started = time.perf_counter()
        groups: dict[str, list[dict]] = {}
        for slide in slides:
            groups.setdefault(slide["pdf_object_key"], []).append(slide)

        queue: Queue = Queue()
        result = {"processed": 0, "failed": 0, "vlm_down": 0, "errors": []}
        result_lock = threading.Lock()
        embedder_error: list[BaseException] = []

        def embed_loop() -> None:
            try:
                while True:
                    item = queue.get()
                    if item is None:
                        return
                    batch = [item]
                    deadline = (
                        time.monotonic() + self.EMBED_BATCH_WINDOW_SECONDS
                    )
                    stop = False
                    while len(batch) < self.EMBED_BATCH:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            break
                        try:
                            nxt = queue.get(timeout=remaining)
                        except Empty:
                            break
                        if nxt is None:
                            stop = True
                            break
                        batch.append(nxt)
                    self._embed_batch(batch, result, result_lock)
                    if stop:
                        return
            except BaseException as exc:  # noqa: BLE001
                logger.exception("Embedding worker dừng bất thường")
                embedder_error.append(exc)

        embedder = threading.Thread(
            target=embed_loop, daemon=True, name="ingest-embed"
        )
        embedder.start()
        try:
            for key, group in groups.items():
                slide_ids = [slide["slide_id"] for slide in group]
                self._mark_many(slide_ids, "pending")
                try:
                    document, _data = self._open_document(key)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Không mở được PDF %s", key)
                    self._mark_many(slide_ids, "failed", _error_text(exc))
                    self._failed(result, result_lock, group, exc)
                    continue

                render_lock = threading.Lock()
                try:
                    with ThreadPoolExecutor(
                        max_workers=self.MAX_WORKERS
                    ) as pool:
                        futures = {
                            pool.submit(
                                self._prepare_slide, slide, document, render_lock
                            ): slide
                            for slide in group
                        }
                        for future in as_completed(futures):
                            slide = futures[future]
                            try:
                                queue.put(future.result())
                            except VLMUnavailableError as exc:
                                self._mark(
                                    slide["slide_id"], "failed", _error_text(exc)
                                )
                                self._failed(
                                    result, result_lock, [slide], exc, vlm_down=True
                                )
                            except Exception as exc:  # noqa: BLE001
                                logger.exception(
                                    "Bỏ qua slide %s do lỗi xử lý",
                                    slide["slide_id"],
                                )
                                self._mark(
                                    slide["slide_id"], "failed", _error_text(exc)
                                )
                                self._failed(result, result_lock, [slide], exc)
                finally:
                    document.close()
        finally:
            queue.put(None)
            embedder.join()

        if embedder_error:
            raise RuntimeError(
                "Embedding worker dừng bất thường"
            ) from embedder_error[0]

        logger.info(
            "ingest done slides=%s processed=%s failed=%s wall_ms=%.0f",
            len(slides),
            result["processed"],
            result["failed"],
            (time.perf_counter() - started) * 1000,
        )
        # Chỉ báo lỗi transport khi không có slide nào thành công. Nếu đã có
        # slide ready, trả counts để backend giữ nguyên kết quả thành công và
        # chỉ retry các slide còn failed/pending.
        if result["vlm_down"] and result["processed"] == 0:
            raise VLMUnavailableError(
                "VLM tạm thời không khả dụng cho một hoặc nhiều slide."
            )
        return result["processed"], result["failed"], result["errors"]

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
