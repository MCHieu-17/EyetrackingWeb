"""Đồng bộ trạng thái ingest slide version sang chatbot/pgvector.

`slide_documents` là nguồn trạng thái duy nhất cho RAG. Backend gọi chatbot
`/ingest/*`; chatbot đọc nội dung published qua view và ghi transcript/vector.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.course import (
    CourseVersionItem,
    LessonVersionSlide,
)
from app.models.media import SlideDocument

logger = logging.getLogger(__name__)

PENDING = "pending"
READY = "ready"
FAILED = "failed"
PIPELINE_VERSION = "rag-v2"
MODEL_VERSION = "qwen3-embedding-0.6b"

_ingest_client: httpx.AsyncClient | None = None

# Chatbot serialize mọi job ingest bằng một lock, nên backend cũng chỉ nên
# chạy một job tại một thời điểm. Publish + reindex + content-worker có thể
# cùng schedule ingest cho cùng slide; job thứ hai sẽ thấy slide đã ready và
# trả về ngay thay vì mark pending rồi ingest lại.
_ingest_lock = asyncio.Lock()


@asynccontextmanager
async def _single_flight(key: str):
    """Chỉ cho một job ingest chạy trong process này; job trùng bị bỏ qua."""
    if _ingest_lock.locked():
        logger.info("Ingest %s đang chạy — bỏ qua lần gọi trùng", key)
        yield False
        return
    await _ingest_lock.acquire()
    try:
        yield True
    finally:
        _ingest_lock.release()


def _client() -> httpx.AsyncClient:
    global _ingest_client
    if _ingest_client is None:
        _ingest_client = httpx.AsyncClient(
            timeout=settings.chatbot_ingest_timeout_seconds,
            headers={"X-Chatbot-Token": settings.chatbot_internal_token},
        )
    return _ingest_client


async def close_ingest_client() -> None:
    global _ingest_client
    if _ingest_client is not None:
        await _ingest_client.aclose()
        _ingest_client = None


async def _mark_many(
    session, slide_version_ids: list[str], status: str, error: str | None = None
) -> None:
    # Giữ thứ tự nhưng loại trùng: một slide version có thể xuất hiện ở nhiều
    # item, và ON CONFLICT không cho update cùng một row hai lần trong một câu.
    unique_ids = list(dict.fromkeys(slide_version_ids))
    if not unique_ids:
        return
    now = datetime.now(timezone.utc)
    stmt = pg_insert(SlideDocument).values(
        [
            {
                "slide_version_id": slide_version_id,
                "pipeline_version": PIPELINE_VERSION,
                "model_version": MODEL_VERSION,
                "transcript": "",
                "embedding": None,
                "ingestion_state": status,
                "ingestion_error": error,
                "updated_at": now,
            }
            for slide_version_id in unique_ids
        ]
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["slide_version_id"],
        set_={
            "ingestion_state": stmt.excluded.ingestion_state,
            "ingestion_error": stmt.excluded.ingestion_error,
            "updated_at": stmt.excluded.updated_at,
        },
        # Không kéo slide đã ready về pending: một job khác có thể vừa ingest
        # xong trong lúc job này tính danh sách target.
        where=SlideDocument.ingestion_state != READY,
    )
    await session.execute(stmt)
    await session.commit()


async def _mark_failed_unready(
    session, slide_version_ids: list[str], error: str
) -> None:
    """Đánh dấu failed các slide còn PENDING sau khi batch lỗi.

    Chatbot có thể đã ingest thành công một phần rồi mới lỗi (VLM/DB). Không
    được ghi đè slide đã ready (mất kết quả tốt) hoặc slide chatbot đã đánh
    dấu failed với lỗi cụ thể hơn.
    """
    unique_ids = list(dict.fromkeys(slide_version_ids))
    if not unique_ids:
        return
    await session.execute(
        update(SlideDocument)
        .where(
            SlideDocument.slide_version_id.in_(unique_ids),
            SlideDocument.ingestion_state == PENDING,
        )
        .values(
            ingestion_state=FAILED,
            ingestion_error=error,
            updated_at=datetime.now(timezone.utc),
        )
    )
    await session.commit()


async def _call(path: str, payload: dict) -> dict:
    if not settings.chatbot_ready:
        raise RuntimeError("Chatbot chưa được cấu hình")

    last_error: Exception | None = None
    attempts = max(1, settings.chatbot_ingest_attempts)
    for attempt in range(1, attempts + 1):
        try:
            response = await _client().post(
                f"{settings.chatbot_url_resolved.rstrip('/')}{path}",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            # Giữ nguyên body lỗi của chatbot (vd "password authentication
            # failed", "Không truy cập được PostgreSQL...") để UI hiển thị
            # đúng nguyên nhân thay vì chỉ "500 Internal Server Error".
            detail = exc.response.text.strip()
            last_error = RuntimeError(
                f"HTTP {exc.response.status_code}: {detail[:500]}"
                if detail
                else str(exc)
            )
            if 400 <= exc.response.status_code < 500 and exc.response.status_code != 429:
                break
        except httpx.HTTPError as exc:
            last_error = exc
        if attempt < attempts:
            await asyncio.sleep(settings.chatbot_ingest_backoff_seconds * attempt)

    raise RuntimeError(f"Chatbot ingest thất bại: {last_error}")


async def _slide_ids_for_course_version(
    session, course_version_id: str
) -> list[str]:
    rows = (
        await session.execute(
            select(LessonVersionSlide.slide_version_id)
            .join(
                CourseVersionItem,
                CourseVersionItem.lesson_version_id
                == LessonVersionSlide.lesson_version_id,
            )
            .where(CourseVersionItem.course_version_id == course_version_id)
            .order_by(
                CourseVersionItem.position, LessonVersionSlide.position
            )
        )
    ).scalars()
    return [str(row) for row in rows]


async def _slide_ids_for_lesson_version(
    session, lesson_version_id: str
) -> list[str]:
    rows = (
        await session.execute(
            select(LessonVersionSlide.slide_version_id)
            .where(LessonVersionSlide.lesson_version_id == lesson_version_id)
            .order_by(LessonVersionSlide.position)
        )
    ).scalars()
    return [str(row) for row in rows]


async def _ready_slide_ids(session, slide_ids: list[str]) -> set[str]:
    if not slide_ids:
        return set()
    rows = (
        await session.execute(
            select(SlideDocument.slide_version_id).where(
                SlideDocument.slide_version_id.in_(slide_ids),
                SlideDocument.ingestion_state == READY,
            )
        )
    ).scalars()
    return {str(row) for row in rows}


async def _status_counts(session, slide_ids: list[str]) -> dict[str, int]:
    if not slide_ids:
        return {"ready": 0, "failed": 0, "pending": 0, "total": 0}
    rows = (
        await session.execute(
            select(SlideDocument.ingestion_state, func.count())
            .where(SlideDocument.slide_version_id.in_(slide_ids))
            .group_by(SlideDocument.ingestion_state)
        )
    ).all()
    counts = {status: int(count) for status, count in rows}
    return {
        "ready": counts.get(READY, 0),
        "failed": counts.get(FAILED, 0),
        "pending": counts.get(PENDING, 0),
        "total": len(slide_ids),
    }


def _chunks(items: list[str], size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


async def _sync(
    session,
    *,
    all_slide_ids: list[str],
    path: str,
    payload: dict,
    only_pending: bool,
) -> dict[str, int]:
    """Index các slide chưa ready rồi trả về trạng thái của toàn bộ slide.

    Chia thành batch nhỏ: VLM + embedding chạy tuần tự nên một bài 70+ trang có
    thể vượt timeout HTTP nếu gửi một request. Batch còn giúp slide đã xong
    được giữ nguyên khi batch sau lỗi.
    """
    target_ids = all_slide_ids
    if only_pending:
        ready_ids = await _ready_slide_ids(session, all_slide_ids)
        target_ids = [
            slide_id for slide_id in all_slide_ids if slide_id not in ready_ids
        ]
    if not target_ids:
        return await _status_counts(session, all_slide_ids)

    await _mark_many(session, target_ids, PENDING)
    batch_size = max(1, settings.chatbot_ingest_batch_size)
    batches = list(_chunks(target_ids, batch_size))
    for index, batch in enumerate(batches, start=1):
        try:
            await _call(path, {**payload, "slide_version_ids": batch})
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Ingest %s batch %s/%s thất bại: %s",
                path,
                index,
                len(batches),
                exc,
            )
            await _mark_failed_unready(session, batch, str(exc)[:500])
    return await _status_counts(session, all_slide_ids)


async def course_version_ingest_status_in_session(
    session, course_version_id: str
) -> dict[str, int]:
    slide_ids = await _slide_ids_for_course_version(session, course_version_id)
    return await _status_counts(session, slide_ids)


async def course_version_ingest_status(course_version_id: str) -> dict[str, int]:
    """Chỉ đọc trạng thái index, không gọi chatbot."""
    async with SessionLocal() as session:
        return await course_version_ingest_status_in_session(
            session, course_version_id
        )


async def mark_course_version_pending_in_session(
    session, course_version_id: str
) -> int:
    slide_ids = await _slide_ids_for_course_version(session, course_version_id)
    ready_ids = await _ready_slide_ids(session, slide_ids)
    target_ids = [
        slide_id for slide_id in slide_ids if slide_id not in ready_ids
    ]
    await _mark_many(session, target_ids, PENDING)
    return len(target_ids)


async def mark_course_version_pending(course_version_id: str) -> int:
    """Đánh dấu pending ngay để UI bắt đầu poll trước khi job nền chạy."""
    async with SessionLocal() as session:
        return await mark_course_version_pending_in_session(
            session, course_version_id
        )


async def mark_lesson_version_pending(lesson_version_id: str) -> int:
    async with SessionLocal() as session:
        slide_ids = await _slide_ids_for_lesson_version(
            session, lesson_version_id
        )
        ready_ids = await _ready_slide_ids(session, slide_ids)
        target_ids = [
            slide_id for slide_id in slide_ids if slide_id not in ready_ids
        ]
        await _mark_many(session, target_ids, PENDING)
        return len(target_ids)


async def sync_course_version(
    course_version_id: str,
    include_draft: bool = False,
    only_pending: bool = False,
) -> dict[str, int]:
    if not settings.chatbot_ready:
        logger.warning(
            "Chatbot chưa cấu hình — bỏ qua ingest course version %s",
            course_version_id,
        )
        return await course_version_ingest_status(course_version_id)
    async with _single_flight(f"course:{course_version_id}") as acquired:
        if not acquired:
            logger.info(
                "Ingest course version %s đang chạy — bỏ qua lần gọi trùng",
                course_version_id,
            )
            return await course_version_ingest_status(course_version_id)
        async with SessionLocal() as session:
            slide_ids = await _slide_ids_for_course_version(
                session, course_version_id
            )
            return await _sync(
                session,
                all_slide_ids=slide_ids,
                path="/ingest/course-version",
                payload={
                    "course_version_id": course_version_id,
                    "include_draft": include_draft,
                },
                only_pending=only_pending,
            )


async def sync_lesson_version(
    lesson_version_id: str,
    include_draft: bool = False,
    only_pending: bool = False,
) -> dict[str, int]:
    if not settings.chatbot_ready:
        logger.warning(
            "Chatbot chưa cấu hình — bỏ qua ingest lesson version %s",
            lesson_version_id,
        )
        async with SessionLocal() as session:
            slide_ids = await _slide_ids_for_lesson_version(
                session, lesson_version_id
            )
            return await _status_counts(session, slide_ids)
    async with _single_flight(f"lesson:{lesson_version_id}") as acquired:
        if not acquired:
            logger.info(
                "Ingest lesson version %s đang chạy — bỏ qua lần gọi trùng",
                lesson_version_id,
            )
            async with SessionLocal() as session:
                slide_ids = await _slide_ids_for_lesson_version(
                    session, lesson_version_id
                )
                return await _status_counts(session, slide_ids)
        async with SessionLocal() as session:
            slide_ids = await _slide_ids_for_lesson_version(
                session, lesson_version_id
            )
            return await _sync(
                session,
                all_slide_ids=slide_ids,
                path="/ingest/lesson-version",
                payload={
                    "lesson_version_id": lesson_version_id,
                    "include_draft": include_draft,
                },
                only_pending=only_pending,
            )
