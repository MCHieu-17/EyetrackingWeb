"""Ingest slide: render ảnh -> VLM mô tả -> embedding -> lưu pgvector.

Mỗi slide được xử lý độc lập: một slide lỗi (ảnh thiếu, PDF hỏng) chỉ bị bỏ qua
chứ không làm hỏng cả batch; riêng lỗi VLM (River AI không gọi được) vẫn được
ném ra để API trả 503 và backend retry.

Chunk theo từng slide: mỗi `lesson_contents` là một chunk, transcript VLM là
`content`. Với slide quá dài, transcript vẫn nằm trong context 32k của Qwen3-
Embedding-0.6B nên không cần cắt nhỏ ở MVP.
"""

import base64
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import openai
import pymupdf
from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from pgvector import Vector
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from app.db import get_pool
from app.services.storage import FileStorage
from app.settings import embedding_dim, embedding_name, vlm_name
from app.workflow.prompts import SLIDE_VLM_PROMPT
from app.workflow.providers import get_embedding, get_vlm

logger = logging.getLogger(__name__)


class VLMUnavailableError(RuntimeError):
    """Không gọi được VLM (River AI): mất mạng, timeout hoặc lỗi tạm thời 5xx/429."""


class VLMOutput(BaseModel):
    transcript: str = Field(
        description=(
            "Faithful Markdown transcription of the slide in reading order. "
            "Preserve original text and table relationships; repeat merged-cell "
            "labels on applicable rows. Include visual descriptions separately "
            'under "Mô tả hình".'
        )
    )


class Ingestion:
    # Số ảnh tải trước, song song với lúc VLM đang xử lý slide hiện tại
    PREFETCH = 4
    # Số slide xử lý song song trong một lesson/course
    MAX_WORKERS = 4
    # DPI render trang PDF nguồn (ảnh raster đã render sẵn thì giữ nguyên pixel)
    PDF_RENDER_DPI = 150

    SLIDE_QUERY = """
        SELECT
            lc.id,
            lc.image_url,
            lc.order_index AS slide_index,
            c.id AS course_id,
            c.title AS course_title,
            m.title AS module_title,
            l.id AS lesson_id,
            l.title AS lesson_title
        FROM lesson_contents lc
        JOIN lessons l ON l.id = lc.lesson_id
        JOIN modules m ON m.id = l.module_id
        JOIN courses c ON c.id = m.course_id
    """

    def __init__(self):
        vlm = get_vlm(vlm_name())
        self.slide_to_text_chain = self._create_chat_messages() | vlm.with_structured_output(
            VLMOutput, method="function_calling"
        )
        self.embedding = get_embedding(embedding_name())
        self.storage = FileStorage()
        self._pool = None
        # sentence-transformers không thread-safe khi chạy song song trên cùng
        # model; VLM vẫn chạy song song, chỉ serialize bước embedding.
        self._embed_lock = threading.Lock()
        self._verify_vector_dim()

    def _connection(self):
        return (self._pool or get_pool()).connection()

    def _verify_vector_dim(self) -> None:
        """Fail-fast nếu EMBEDDING_DIM lệch số chiều cột vector."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT a.atttypmod
                    FROM pg_attribute a
                    WHERE a.attrelid = to_regclass('lesson_content_embedding')
                      AND a.attname = 'embedding'
                    """
                )
                row = cur.fetchone()

        if row is None:
            raise RuntimeError(
                "Không tìm thấy cột lesson_content_embedding.embedding — "
                "hãy chạy migration 024_chatbot_rag.sql trước."
            )

        column_dim = int(row["atttypmod"])
        if column_dim != embedding_dim():
            raise RuntimeError(
                f"EMBEDDING_DIM={embedding_dim()} không khớp VECTOR({column_dim}) của "
                "lesson_content_embedding.embedding. Sửa EMBEDDING_DIM (và "
                "EMBEDDING_NAME/MODEL) cho khớp, hoặc tạo migration đổi số chiều "
                "rồi re-ingest toàn bộ slide."
            )
        logger.info("Embedding dimension khớp DB: vector(%s)", column_dim)

    def _load_slide(self, lesson_content_id: str) -> dict | None:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(self.SLIDE_QUERY + " WHERE lc.id = %s", (lesson_content_id,))
                return cur.fetchone()

    def _load_slides_for_lesson(self, lesson_id: str) -> list[dict]:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    self.SLIDE_QUERY + " WHERE lc.lesson_id = %s ORDER BY lc.order_index",
                    (lesson_id,),
                )
                return list(cur.fetchall())

    def _load_slides_for_course(self, course_id: str) -> list[dict]:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    self.SLIDE_QUERY
                    + " WHERE m.course_id = %s"
                    + " ORDER BY m.order_index, l.order_index, lc.order_index",
                    (course_id,),
                )
                return list(cur.fetchall())

    def _load_pending_slides(self) -> list[dict]:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    self.SLIDE_QUERY
                    + """
                    LEFT JOIN lesson_content_embedding e
                           ON e.lesson_content_id = lc.id
                    WHERE lc.embedding_status <> 'ready'
                       OR e.lesson_content_id IS NULL
                    ORDER BY c.id, m.order_index, l.order_index, lc.order_index
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

    def _load_image(self, source: str) -> str:
        file_bytes = self.storage.load(source)

        with pymupdf.open(stream=file_bytes) as doc:
            if doc.is_pdf:
                pix = doc[0].get_pixmap(dpi=self.PDF_RENDER_DPI, alpha=False)
            else:
                pix = doc[0].get_pixmap(alpha=False)
            return base64.b64encode(pix.tobytes("png")).decode("ascii")

    def _describe_image(self, b64: str) -> str:
        try:
            from app.workflow.workload import ingest_slot
            with ingest_slot():
                return self.slide_to_text_chain.invoke({"b64": b64}).transcript
        except openai.APITimeoutError as exc:
            raise VLMUnavailableError("VLM (River AI) không phản hồi kịp thời gian.") from exc
        except openai.APIConnectionError as exc:
            base = os.getenv("RIVER_BASE_URL", "https://api.river.ai/v1")
            raise VLMUnavailableError(
                f"Không kết nối được VLM (River AI) tại {base}. Kiểm tra mạng và RIVER_BASE_URL."
            ) from exc
        except openai.APIStatusError as exc:
            if exc.status_code == 429 or exc.status_code >= 500:
                raise VLMUnavailableError(
                    f"VLM (River AI) tạm thời không khả dụng (HTTP {exc.status_code})."
                ) from exc
            raise

    def _add_context(self, slide: dict, markdown: str) -> str:
        fields = [
            ("Môn học", slide.get("course_title")),
            ("Chương", slide.get("module_title")),
            ("Bài học", slide.get("lesson_title")),
            ("Slide", str(slide.get("slide_index")) if slide.get("slide_index") else None),
        ]
        context = "\n".join(
            f"{label}: {value.strip()}" for label, value in fields if value and str(value).strip()
        )
        return f"{context}\n\n{markdown}" if context else markdown

    def _mark(self, slide_id: str, status: str, error: str | None = None) -> None:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE lesson_contents
                       SET embedding_status = %s,
                           embedding_error = %s,
                           embedding_updated_at = now()
                     WHERE id = %s
                    """,
                    (status, error, slide_id),
                )

    def _upsert(self, slide: dict, content: str, vector: list[float]) -> None:
        metadata = {
            "course_title": slide.get("course_title"),
            "module_title": slide.get("module_title"),
            "lesson_title": slide.get("lesson_title"),
            "slide_index": slide.get("slide_index"),
            "image_url": slide.get("image_url"),
        }
        with self._connection() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    self.SLIDE_QUERY
                    + " WHERE lc.id = %s AND lc.image_url = %s AND c.deleted_at IS NULL FOR UPDATE OF lc",
                    (slide["id"], slide["image_url"]),
                )
                current = cur.fetchone()
                if current is None:
                    raise LookupError("Slide đã bị xóa hoặc thay thế trong khi ingest")
                cur.execute(
                    """
                    INSERT INTO lesson_content_embedding (
                        lesson_content_id,
                        course_id,
                        lesson_id,
                        content,
                        embedding,
                        metadata,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, now())

                    ON CONFLICT (lesson_content_id)
                    DO UPDATE SET
                        course_id = EXCLUDED.course_id,
                        lesson_id = EXCLUDED.lesson_id,
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata,
                        updated_at = now()
                    """,
                    (
                        slide["id"],
                        slide["course_id"],
                        slide["lesson_id"],
                        content,
                        Vector(vector),
                        Jsonb(metadata),
                    ),
                )

                cur.execute(
                    "UPDATE lesson_contents SET embedding_status = 'ready', embedding_error = NULL, embedding_updated_at = now() WHERE id = %s",
                    (slide["id"],),
                )

    def _embed_slide(self, slide: dict) -> None:
        self._mark(slide["id"], "pending")
        try:
            b64 = self._load_image(slide["image_url"])
            markdown = self._describe_image(b64)
            content = self._add_context(slide, markdown)
            with self._embed_lock:
                vector = self.embedding.embed_documents([content])[0]
            self._upsert(slide, content, vector)
        except VLMUnavailableError as exc:
            self._mark(slide["id"], "failed", str(exc)[:500])
            raise
        except Exception as exc:
            logger.exception("Bỏ qua slide %s do lỗi xử lý", slide.get("id"))
            self._mark(slide["id"], "failed", str(exc)[:500])
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
                    errors.append(f"{slide['id']}: {exc}")
                except Exception as exc:
                    failed += 1
                    errors.append(f"{slide['id']}: {exc}")

        # Nếu toàn bộ slide lỗi vì VLM không gọi được -> 503 để backend retry.
        if vlm_down:
            raise VLMUnavailableError(
                "VLM (River AI) tạm thời không khả dụng cho một hoặc nhiều slide."
            )

        return processed, failed, errors

    def embed_slide(self, lesson_content_id: str) -> tuple[int, int, list[str]]:
        slide = self._load_slide(lesson_content_id)
        if slide is None:
            raise LookupError(lesson_content_id)
        return self._process_slides([slide])

    def embed_lesson(self, lesson_id: str) -> tuple[int, int, list[str]]:
        slides = self._load_slides_for_lesson(lesson_id)
        if not slides:
            raise LookupError(lesson_id)
        return self._process_slides(slides)

    def embed_course(self, course_id: str) -> tuple[int, int, list[str]]:
        slides = self._load_slides_for_course(course_id)
        if not slides:
            raise LookupError(course_id)
        return self._process_slides(slides)

    def reindex_all(self) -> tuple[int, int, list[str]]:
        slides = self._load_pending_slides()
        if not slides:
            return 0, 0, []
        return self._process_slides(slides)

    def close(self) -> None:
        # storage.http do Ingestion sở hữu. `self.embedding` là client dùng chung
        # (registry) nên không đóng ở đây.
        self.storage.close()
