"""Hàng đợi index RAG dùng chung bảng `background_jobs`."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.background_job import BackgroundJob
from app.services import embedding
from app.services.job_queue import claim_next_jobs
from app.services.job_queue import recover_stale_jobs as recover_stale_kind

logger = logging.getLogger(__name__)

INDEX_KIND = "index_slides"
ANALYZE_KIND = "analyze_lesson"
ACTIVE_STATUSES = ("queued", "processing")


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _enqueue(
    db: AsyncSession, *, lesson_id: str, kind: str, payload: dict | None = None
) -> BackgroundJob:
    existing = (
        await db.execute(
            select(BackgroundJob)
            .where(
                BackgroundJob.lesson_id == lesson_id,
                BackgroundJob.kind == kind,
                BackgroundJob.status.in_(ACTIVE_STATUSES),
            )
            .order_by(BackgroundJob.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.payload = {**(existing.payload or {}), **(payload or {})}
        return existing

    job = BackgroundJob(
        lesson_id=lesson_id,
        kind=kind,
        status="queued",
        payload=payload or {},
    )
    db.add(job)
    await db.flush()
    return job


async def enqueue_index_lesson(
    db: AsyncSession, lesson_id: str, *, force: bool = False
) -> BackgroundJob:
    return await _enqueue(
        db, lesson_id=lesson_id, kind=INDEX_KIND, payload={"force": force}
    )


async def enqueue_course_index(
    db: AsyncSession, course_id: str, *, force: bool = False
) -> int:
    from app.models.course import CourseModule, Lesson

    lesson_ids = (
        await db.execute(
            select(Lesson.id)
            .join(CourseModule, CourseModule.id == Lesson.module_id)
            .where(CourseModule.course_id == course_id, Lesson.kind == "lesson")
        )
    ).scalars().all()
    for lesson_id in lesson_ids:
        await enqueue_index_lesson(db, lesson_id, force=force)
    return len(lesson_ids)


async def enqueue_analysis_lesson(
    db: AsyncSession, lesson_id: str
) -> BackgroundJob:
    return await _enqueue(db, lesson_id=lesson_id, kind=ANALYZE_KIND)


async def claim_next_job(db: AsyncSession) -> BackgroundJob | None:
    jobs = await claim_next_jobs(db, kind=INDEX_KIND, limit=1)
    return jobs[0] if jobs else None


async def process_job(job_id: str) -> None:
    async with SessionLocal() as db:
        job = await db.get(BackgroundJob, job_id)
        if job is None:
            return
        try:
            force = bool((job.payload or {}).get("force"))
            await embedding.sync_lesson(job.lesson_id, only_pending=not force)
        except Exception as exc:  # noqa: BLE001
            now = _now()
            job.error = str(exc)[:1000]
            job.finished_at = now
            job.updated_at = now
            if job.attempts < job.max_attempts:
                job.status = "queued"
                logger.warning(
                    "Index job %s lỗi (lần %s/%s), sẽ thử lại: %s",
                    job.id,
                    job.attempts,
                    job.max_attempts,
                    exc,
                )
            else:
                job.status = "failed"
                logger.error("Index job %s thất bại: %s", job.id, exc)
            await db.commit()
            return

        now = _now()
        job.status = "ready"
        job.error = None
        job.finished_at = now
        job.updated_at = now
        await db.commit()


async def recover_stale_jobs(
    db: AsyncSession, *, stale_seconds: int | None = None
) -> int:
    seconds = (
        settings.embedding_worker_stale_seconds
        if stale_seconds is None
        else stale_seconds
    )
    return await recover_stale_kind(
        db, kind=INDEX_KIND, stale_seconds=seconds
    )


async def process_pending_jobs(limit: int = 1) -> int:
    job_ids: list[str] = []
    async with SessionLocal() as db:
        await recover_stale_jobs(db)
        for _ in range(limit):
            job = await claim_next_job(db)
            if job is None:
                break
            job_ids.append(job.id)

    for job_id in job_ids:
        await process_job(job_id)
    return len(job_ids)
