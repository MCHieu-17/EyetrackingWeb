"""Đồng bộ trạng thái embedding slide sang dịch vụ chatbot (pgvector).

Backend là nguồn dữ liệu slide; chatbot giữ vector trong bảng
`lesson_content_embedding`. Module này:

- Gọi `/ingest/lesson` (hoặc `/ingest/slide`) và cập nhật trạng thái
  (`pending` → `ready` / `failed`) trên `lesson_contents`.
- Cung cấp backfill toàn bộ qua `/ingest/reindex-all`.

Các hàm được thiết kế để chạy trong BackgroundTasks; trạng thái được cập nhật
bằng session riêng vì background task chạy sau khi response đã trả về.
"""

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import func, select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.course import Lesson, LessonContent, Module

logger = logging.getLogger(__name__)

PENDING = "pending"
READY = "ready"
FAILED = "failed"


async def _mark(
    session, slide_id: str, status: str, error: str | None = None
) -> None:
    slide = await session.get(LessonContent, slide_id)
    if slide is None:
        return
    slide.embedding_status = status
    slide.embedding_error = error
    slide.embedding_updated_at = datetime.now(timezone.utc)
    await session.commit()


async def _mark_many(
    session, slide_ids: list[str], status: str, error: str | None = None
) -> None:
    if not slide_ids:
        return
    now = datetime.now(timezone.utc)
    rows = (
        await session.execute(
            select(LessonContent).where(LessonContent.id.in_(slide_ids))
        )
    ).scalars()
    for slide in rows:
        slide.embedding_status = status
        slide.embedding_error = error
        slide.embedding_updated_at = now
    await session.commit()


async def _call(path: str, payload: dict) -> dict:
    """Gọi chatbot ingest, retry lỗi tạm thời (5xx/429/connection)."""
    if not settings.chatbot_ready:
        raise RuntimeError("Chatbot chưa được cấu hình")

    last_error: Exception | None = None
    attempts = max(1, settings.chatbot_ingest_attempts)
    for attempt in range(1, attempts + 1):
        try:
            async with httpx.AsyncClient(
                timeout=settings.chatbot_ingest_timeout_seconds,
                headers={"X-Chatbot-Token": settings.chatbot_internal_token},
            ) as client:
                response = await client.post(
                    f"{settings.chatbot_url_resolved.rstrip('/')}{path}",
                    json=payload,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            last_error = exc
            # 4xx: lỗi dữ liệu/cấu hình -> retry vô ích.
            if 400 <= exc.response.status_code < 500 and exc.response.status_code != 429:
                break
        except httpx.HTTPError as exc:
            last_error = exc
        if attempt < attempts:
            await asyncio.sleep(settings.chatbot_ingest_backoff_seconds * attempt)

    raise RuntimeError(f"Chatbot ingest thất bại: {last_error}")


async def _slide_ids_for_lesson(session, lesson_id: str) -> list[str]:
    rows = (
        await session.execute(
            select(LessonContent.id)
            .where(LessonContent.lesson_id == lesson_id)
            .order_by(LessonContent.order_index)
        )
    ).scalars()
    return [str(row) for row in rows]


async def _slide_ids_for_course(session, course_id: str) -> list[str]:
    rows = (
        await session.execute(
            select(LessonContent.id)
            .join(Lesson, Lesson.id == LessonContent.lesson_id)
            .join(Module, Module.id == Lesson.module_id)
            .where(Module.course_id == course_id)
            .order_by(Module.order_index, Lesson.order_index, LessonContent.order_index)
        )
    ).scalars()
    return [str(row) for row in rows]


async def _status_counts(session, slide_ids: list[str]) -> dict[str, int]:
    if not slide_ids:
        return {"ready": 0, "failed": 0}
    rows = (
        await session.execute(
            select(LessonContent.embedding_status, func.count(LessonContent.id))
            .where(LessonContent.id.in_(slide_ids))
            .group_by(LessonContent.embedding_status)
        )
    ).all()
    counts = {status: int(count) for status, count in rows}
    return {
        "ready": counts.get(READY, 0),
        "failed": counts.get(FAILED, 0),
    }


async def sync_slide(slide_id: str) -> dict[str, int]:
    """Ingest một slide (dùng cho add_slide)."""
    if not settings.chatbot_ready:
        logger.warning("Chatbot chưa cấu hình — bỏ qua embedding slide %s", slide_id)
        return {"ready": 0, "failed": 0}

    async with SessionLocal() as session:
        await _mark(session, slide_id, PENDING)
        try:
            await _call("/ingest/slide", {"lesson_content_id": slide_id})
        except Exception as exc:
            logger.warning("Embedding slide %s thất bại: %s", slide_id, exc)
            await _mark(session, slide_id, FAILED, str(exc)[:500])
            return {"ready": 0, "failed": 1}
        return await _status_counts(session, [slide_id])


async def sync_lesson(lesson_id: str) -> dict[str, int]:
    """Ingest toàn bộ slide của một bài học."""
    if not settings.chatbot_ready:
        logger.warning("Chatbot chưa cấu hình — bỏ qua embedding lesson %s", lesson_id)
        return {"ready": 0, "failed": 0}

    async with SessionLocal() as session:
        slide_ids = await _slide_ids_for_lesson(session, lesson_id)
        if not slide_ids:
            return {"ready": 0, "failed": 0}
        await _mark_many(session, slide_ids, PENDING)
        try:
            await _call("/ingest/lesson", {"lesson_id": lesson_id})
        except Exception as exc:
            logger.warning("Embedding lesson %s thất bại: %s", lesson_id, exc)
            await _mark_many(session, slide_ids, FAILED, str(exc)[:500])
            return {"ready": 0, "failed": len(slide_ids)}
        return await _status_counts(session, slide_ids)


async def sync_course(course_id: str) -> dict[str, int]:
    """Ingest toàn bộ slide của một khóa học."""
    if not settings.chatbot_ready:
        logger.warning("Chatbot chưa cấu hình — bỏ qua embedding course %s", course_id)
        return {"ready": 0, "failed": 0}

    async with SessionLocal() as session:
        slide_ids = await _slide_ids_for_course(session, course_id)
        if not slide_ids:
            return {"ready": 0, "failed": 0}
        await _mark_many(session, slide_ids, PENDING)
        try:
            await _call("/ingest/course", {"course_id": course_id})
        except Exception as exc:
            logger.warning("Embedding course %s thất bại: %s", course_id, exc)
            await _mark_many(session, slide_ids, FAILED, str(exc)[:500])
            return {"ready": 0, "failed": len(slide_ids)}
        return await _status_counts(session, slide_ids)


async def reindex_all() -> dict[str, int]:
    """Backfill toàn bộ slide chưa ready (admin/CLI)."""
    if not settings.chatbot_ready:
        return {"ready": 0, "failed": 0}
    try:
        data = await _call("/ingest/reindex-all", {})
    except Exception as exc:
        logger.warning("Reindex all thất bại: %s", exc)
        return {"ready": 0, "failed": 0}
    return {
        "ready": int(data.get("processed", 0)),
        "failed": int(data.get("failed", 0)),
    }


async def counts() -> dict[str, int]:
    """Thống kê trạng thái embedding toàn hệ thống."""
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(LessonContent.embedding_status, func.count(LessonContent.id))
                .group_by(LessonContent.embedding_status)
            )
        ).all()
        return {status: int(count) for status, count in rows}


async def course_counts(course_id: str) -> dict[str, int]:
    """Thống kê trạng thái embedding của một khóa học."""
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(LessonContent.embedding_status, func.count(LessonContent.id))
                .join(Lesson, Lesson.id == LessonContent.lesson_id)
                .join(Module, Module.id == Lesson.module_id)
                .where(Module.course_id == course_id)
                .group_by(LessonContent.embedding_status)
            )
        ).all()
        return {status: int(count) for status, count in rows}
