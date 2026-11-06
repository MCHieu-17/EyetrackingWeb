"""Đồng bộ trạng thái ingest slide version sang chatbot/pgvector.

`slide_documents` là nguồn trạng thái duy nhất cho RAG. Backend gọi chatbot
`/ingest/*`; chatbot đọc nội dung published qua view và ghi transcript/vector.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import func, select
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


async def _mark(
    session, slide_version_id: str, status: str, error: str | None = None
) -> None:
    stmt = pg_insert(SlideDocument).values(
        slide_version_id=slide_version_id,
        pipeline_version=PIPELINE_VERSION,
        model_version=MODEL_VERSION,
        transcript="",
        embedding=None,
        ingestion_state=status,
        ingestion_error=error,
        updated_at=datetime.now(timezone.utc),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["slide_version_id"],
        set_={
            "ingestion_state": stmt.excluded.ingestion_state,
            "ingestion_error": stmt.excluded.ingestion_error,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    await session.execute(stmt)
    await session.commit()


async def _mark_many(
    session, slide_version_ids: list[str], status: str, error: str | None = None
) -> None:
    for slide_version_id in slide_version_ids:
        await _mark(session, slide_version_id, status, error)


async def _call(path: str, payload: dict) -> dict:
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
            if 400 <= exc.response.status_code < 500 and exc.response.status_code != 429:
                break
        except httpx.HTTPError as exc:
            last_error = exc
        if attempt < attempts:
            await asyncio.sleep(settings.chatbot_ingest_backoff_seconds * attempt)

    raise RuntimeError(f"Chatbot ingest thất bại: {last_error}")


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


async def _status_counts(session, slide_ids: list[str]) -> dict[str, int]:
    if not slide_ids:
        return {"ready": 0, "failed": 0}
    rows = (
        await session.execute(
            select(SlideDocument.ingestion_state, func.count())
            .where(SlideDocument.slide_version_id.in_(slide_ids))
            .group_by(SlideDocument.ingestion_state)
        )
    ).all()
    counts = {status: int(count) for status, count in rows}
    return {"ready": counts.get(READY, 0), "failed": counts.get(FAILED, 0)}


async def sync_slide(slide_version_id: str) -> dict[str, int]:
    if not settings.chatbot_ready:
        logger.warning("Chatbot chưa cấu hình — bỏ qua ingest slide %s", slide_version_id)
        return {"ready": 0, "failed": 0}
    async with SessionLocal() as session:
        await _mark(session, slide_version_id, PENDING)
        try:
            await _call("/ingest/slide", {"slide_version_id": slide_version_id})
        except Exception as exc:  # noqa: BLE001
            logger.warning("Ingest slide %s thất bại: %s", slide_version_id, exc)
            await _mark(session, slide_version_id, FAILED, str(exc)[:500])
            return {"ready": 0, "failed": 1}
        return await _status_counts(session, [slide_version_id])


async def sync_lesson_version(lesson_version_id: str) -> dict[str, int]:
    if not settings.chatbot_ready:
        logger.warning(
            "Chatbot chưa cấu hình — bỏ qua ingest lesson version %s",
            lesson_version_id,
        )
        return {"ready": 0, "failed": 0}
    async with SessionLocal() as session:
        slide_ids = await _slide_ids_for_lesson_version(session, lesson_version_id)
        if not slide_ids:
            return {"ready": 0, "failed": 0}
        await _mark_many(session, slide_ids, PENDING)
        try:
            await _call(
                "/ingest/lesson-version",
                {"lesson_version_id": lesson_version_id},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Ingest lesson version %s thất bại: %s", lesson_version_id, exc
            )
            await _mark_many(session, slide_ids, FAILED, str(exc)[:500])
            return {"ready": 0, "failed": len(slide_ids)}
        return await _status_counts(session, slide_ids)


async def sync_course_version(course_version_id: str) -> dict[str, int]:
    if not settings.chatbot_ready:
        logger.warning(
            "Chatbot chưa cấu hình — bỏ qua ingest course version %s",
            course_version_id,
        )
        return {"ready": 0, "failed": 0}
    async with SessionLocal() as session:
        slide_ids = await _slide_ids_for_course_version(session, course_version_id)
        if not slide_ids:
            return {"ready": 0, "failed": 0}
        await _mark_many(session, slide_ids, PENDING)
        try:
            await _call(
                "/ingest/course-version",
                {"course_version_id": course_version_id},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Ingest course version %s thất bại: %s", course_version_id, exc
            )
            await _mark_many(session, slide_ids, FAILED, str(exc)[:500])
            return {"ready": 0, "failed": len(slide_ids)}
        return await _status_counts(session, slide_ids)


async def reindex_all() -> dict[str, int]:
    if not settings.chatbot_ready:
        return {"ready": 0, "failed": 0}
    try:
        data = await _call("/ingest/reindex-all", {})
    except Exception as exc:  # noqa: BLE001
        logger.warning("Reindex all thất bại: %s", exc)
        return {"ready": 0, "failed": 0}
    return {
        "ready": int(data.get("processed", 0)),
        "failed": int(data.get("failed", 0)),
    }


async def counts() -> dict[str, int]:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(SlideDocument.ingestion_state, func.count())
                .group_by(SlideDocument.ingestion_state)
            )
        ).all()
        return {status: int(count) for status, count in rows}


async def course_counts(course_version_id: str) -> dict[str, int]:
    async with SessionLocal() as session:
        slide_ids = await _slide_ids_for_course_version(session, course_version_id)
        return await _status_counts(session, slide_ids)
