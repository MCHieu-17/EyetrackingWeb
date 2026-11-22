"""Đồng bộ index RAG của slide sang chatbot/pgvector.

`slides` là nguồn trạng thái duy nhất: transcript/embedding/index_status nằm
cùng một row. Backend gọi chatbot `/ingest/slides`; chatbot đọc PDF qua view
outline và cập nhật trực tiếp các slide đó.
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from sqlalchemy import func, select, update

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.course import CourseModule, Lesson, Slide

logger = logging.getLogger(__name__)

PENDING = "pending"
READY = "ready"
FAILED = "failed"
NONE = "none"
PIPELINE_VERSION = "rag-v2"

_ingest_client: httpx.AsyncClient | None = None
_ingest_locks: dict[str, asyncio.Lock] = {}


@asynccontextmanager
async def _single_flight(key: str):
    """Cho một job ingest chạy cho mỗi key; key khác vẫn chạy độc lập."""
    lock = _ingest_locks.setdefault(key, asyncio.Lock())
    if lock.locked():
        logger.info("Ingest %s đang chạy — bỏ qua lần gọi trùng", key)
        yield False
        return
    await lock.acquire()
    try:
        yield True
    finally:
        lock.release()
        if _ingest_locks.get(key) is lock:
            _ingest_locks.pop(key, None)


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
    session, slide_ids: list[str], status: str, error: str | None = None
) -> None:
    unique_ids = list(dict.fromkeys(slide_ids))
    if not unique_ids:
        return
    await session.execute(
        update(Slide)
        .where(Slide.id.in_(unique_ids))
        .values(
            index_status=status,
            index_error=error,
            pipeline_version=PIPELINE_VERSION,
            updated_at=datetime.now(timezone.utc),
        )
    )
    await session.commit()


async def _mark_failed_unready(
    session, slide_ids: list[str], error: str
) -> None:
    """Đánh dấu failed các slide còn pending sau khi batch lỗi.

    Chatbot có thể đã ingest xong một phần rồi mới lỗi transport. Không ghi
    đè slide đã ready hoặc lỗi cụ thể chatbot đã ghi cho slide failed.
    """
    unique_ids = list(dict.fromkeys(slide_ids))
    if not unique_ids:
        return
    await session.execute(
        update(Slide)
        .where(
            Slide.id.in_(unique_ids),
            Slide.index_status == PENDING,
        )
        .values(
            index_status=FAILED,
            index_error=error,
            updated_at=datetime.now(timezone.utc),
        )
    )
    await session.commit()


async def _status_counts(session, lesson_id: str) -> dict[str, int]:
    rows = (
        await session.execute(
            select(Slide.index_status, func.count())
            .where(Slide.lesson_id == lesson_id)
            .group_by(Slide.index_status)
        )
    ).all()
    counts = {status: int(count) for status, count in rows}
    return {
        "ready": counts.get(READY, 0),
        "failed": counts.get(FAILED, 0),
        "pending": counts.get(PENDING, 0) + counts.get(NONE, 0),
        "total": sum(counts.values()),
    }


async def _slide_ids(session, lesson_id: str) -> list[str]:
    return list(
        (
            await session.execute(
                select(Slide.id)
                .where(Slide.lesson_id == lesson_id)
                .order_by(Slide.position)
            )
        ).scalars()
    )


async def _call(payload: dict) -> dict:
    if not settings.chatbot_ready:
        raise RuntimeError("Chatbot chưa được cấu hình")

    last_error: Exception | None = None
    attempts = max(1, settings.chatbot_ingest_attempts)
    for attempt in range(1, attempts + 1):
        try:
            response = await _client().post(
                f"{settings.chatbot_url_resolved.rstrip('/')}/ingest/slides",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
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


def _chunks(items: list[str], size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


async def _sync(
    session,
    *,
    lesson_id: str,
    all_slide_ids: list[str],
    only_pending: bool,
) -> dict[str, int]:
    if not all_slide_ids:
        return await _status_counts(session, lesson_id)

    if only_pending:
        ready_ids = set(
            (
                await session.execute(
                    select(Slide.id).where(
                        Slide.id.in_(all_slide_ids),
                        Slide.index_status == READY,
                    )
                )
            ).scalars()
        )
        target_ids = [sid for sid in all_slide_ids if sid not in ready_ids]
    else:
        target_ids = all_slide_ids

    if not target_ids:
        return await _status_counts(session, lesson_id)

    await _mark_many(session, target_ids, PENDING)
    batch_size = max(1, settings.chatbot_ingest_batch_size)
    for batch in _chunks(target_ids, batch_size):
        started = time.perf_counter()
        try:
            await _call({"slide_ids": batch})
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Ingest lesson %s batch thất bại sau %.1fs: %s",
                lesson_id,
                time.perf_counter() - started,
                exc,
            )
            await _mark_failed_unready(session, batch, str(exc)[:500])
        else:
            logger.info(
                "Ingest lesson %s batch=%s wall=%.1fs",
                lesson_id,
                len(batch),
                time.perf_counter() - started,
            )
    return await _status_counts(session, lesson_id)


async def lesson_ingest_status(lesson_id: str) -> dict[str, int]:
    async with SessionLocal() as session:
        return await _status_counts(session, lesson_id)


async def course_ingest_status_in_session(
    session, course_id: str
) -> dict[str, int]:
    rows = (
        await session.execute(
            select(Slide.index_status, func.count(Slide.id))
            .join(Lesson, Lesson.id == Slide.lesson_id)
            .join(CourseModule, CourseModule.id == Lesson.module_id)
            .where(CourseModule.course_id == course_id)
            .group_by(Slide.index_status)
        )
    ).all()
    counts = {status: int(count) for status, count in rows}
    return {
        "ready": counts.get(READY, 0),
        "failed": counts.get(FAILED, 0),
        "pending": counts.get(PENDING, 0) + counts.get(NONE, 0),
        "total": sum(counts.values()),
    }


async def mark_lesson_pending(lesson_id: str) -> int:
    async with SessionLocal() as session:
        ids = await _slide_ids(session, lesson_id)
        await _mark_many(session, ids, PENDING)
        return len(ids)


async def mark_course_pending_in_session(session, course_id: str) -> int:
    rows = (
        await session.execute(
            select(Slide.id)
            .join(Lesson, Lesson.id == Slide.lesson_id)
            .join(CourseModule, CourseModule.id == Lesson.module_id)
            .where(CourseModule.course_id == course_id)
        )
    ).scalars().all()
    await _mark_many(session, list(rows), PENDING)
    return len(rows)


async def sync_lesson(lesson_id: str, only_pending: bool = True) -> dict[str, int]:
    if not settings.chatbot_ready:
        logger.warning("Chatbot chưa cấu hình — bỏ qua ingest lesson %s", lesson_id)
        return await lesson_ingest_status(lesson_id)
    async with _single_flight(f"lesson:{lesson_id}") as acquired:
        if not acquired:
            return await lesson_ingest_status(lesson_id)
        async with SessionLocal() as session:
            slide_ids = await _slide_ids(session, lesson_id)
            return await _sync(
                session,
                lesson_id=lesson_id,
                all_slide_ids=slide_ids,
                only_pending=only_pending,
            )
