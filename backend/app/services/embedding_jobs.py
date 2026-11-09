"""Hàng đợi job đồng bộ embedding (RAG ingest) trong PostgreSQL.

API chỉ ghi job vào `embedding_jobs`; worker riêng (`app.embedding_worker`)
claim và gọi `app.services.embedding.sync_*`. Nhờ vậy job sống sót qua
restart và nhiều backend replica dùng chung một hàng đợi.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.embedding_job import EmbeddingJob
from app.services import embedding

logger = logging.getLogger(__name__)

COURSE_VERSION = "course_version"
LESSON_VERSION = "lesson_version"
ACTIVE_STATUSES = ("pending", "running")


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _enqueue(
    db: AsyncSession,
    *,
    kind: str,
    target_id: str,
    include_draft: bool,
    force: bool,
) -> EmbeddingJob:
    """Trả job pending/running trùng cấu hình, hoặc tạo job mới.

    Không commit; caller commit cùng transaction nghiệp vụ. Job trùng chỉ là
    tối ưu: nếu hai request đua nhau, cả hai job đều idempotent khi chạy.
    """
    existing = (
        await db.execute(
            select(EmbeddingJob)
            .where(
                EmbeddingJob.kind == kind,
                EmbeddingJob.target_id == target_id,
                EmbeddingJob.include_draft == include_draft,
                EmbeddingJob.force == force,
                EmbeddingJob.status.in_(ACTIVE_STATUSES),
            )
            .order_by(EmbeddingJob.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    job = EmbeddingJob(
        kind=kind,
        target_id=target_id,
        include_draft=include_draft,
        force=force,
    )
    db.add(job)
    await db.flush()
    return job


async def enqueue_course_version(
    db: AsyncSession,
    course_version_id: str,
    *,
    include_draft: bool = False,
    force: bool = False,
) -> EmbeddingJob:
    return await _enqueue(
        db,
        kind=COURSE_VERSION,
        target_id=course_version_id,
        include_draft=include_draft,
        force=force,
    )


async def enqueue_lesson_version(
    db: AsyncSession,
    lesson_version_id: str,
    *,
    include_draft: bool = False,
    force: bool = False,
) -> EmbeddingJob:
    return await _enqueue(
        db,
        kind=LESSON_VERSION,
        target_id=lesson_version_id,
        include_draft=include_draft,
        force=force,
    )


async def claim_next_job(db: AsyncSession) -> EmbeddingJob | None:
    """Khóa job pending cũ nhất (bỏ qua job replica khác đang giữ) và đánh dấu running."""
    job = (
        await db.execute(
            select(EmbeddingJob)
            .where(EmbeddingJob.status == "pending")
            .order_by(EmbeddingJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
    ).scalar_one_or_none()
    if job is None:
        return None

    now = _now()
    job.status = "running"
    job.started_at = now
    job.attempts += 1
    job.updated_at = now
    await db.commit()
    return job


async def process_job(job_id: str) -> None:
    """Chạy một job đã claim; lỗi được ghi lại và retry tới `max_attempts`."""
    async with SessionLocal() as db:
        job = await db.get(EmbeddingJob, job_id)
        if job is None:
            logger.warning("Embedding job %s không còn tồn tại", job_id)
            return

        try:
            if job.kind == COURSE_VERSION:
                await embedding.sync_course_version(
                    job.target_id, job.include_draft, job.force
                )
            elif job.kind == LESSON_VERSION:
                await embedding.sync_lesson_version(
                    job.target_id, job.include_draft, job.force
                )
            else:
                raise ValueError(f"Loại embedding job không hợp lệ: {job.kind}")
        except Exception as exc:  # noqa: BLE001
            now = _now()
            job.error = str(exc)[:1000]
            job.finished_at = now
            job.updated_at = now
            if job.attempts < job.max_attempts:
                job.status = "pending"
                logger.warning(
                    "Embedding job %s lỗi (lần %s/%s), sẽ thử lại: %s",
                    job.id,
                    job.attempts,
                    job.max_attempts,
                    exc,
                )
            else:
                job.status = "failed"
                logger.error(
                    "Embedding job %s thất bại sau %s lần: %s",
                    job.id,
                    job.attempts,
                    exc,
                )
            await db.commit()
            return

        now = _now()
        job.status = "completed"
        job.error = None
        job.finished_at = now
        job.updated_at = now
        await db.commit()


async def recover_stale_jobs(
    db: AsyncSession, *, stale_seconds: int | None = None
) -> int:
    """Đưa job running quá lâu trở lại pending (hoặc failed nếu hết lượt).

    Worker chết giữa chừng không còn giữ lock; job sẽ kẹt running mãi nếu
    không có bước này.
    """
    seconds = (
        settings.embedding_worker_stale_seconds
        if stale_seconds is None
        else stale_seconds
    )
    if seconds <= 0:
        return 0
    cutoff = _now() - timedelta(seconds=seconds)
    jobs = (
        await db.execute(
            select(EmbeddingJob)
            .where(
                EmbeddingJob.status == "running",
                EmbeddingJob.started_at < cutoff,
            )
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()
    now = _now()
    for job in jobs:
        job.updated_at = now
        if job.attempts < job.max_attempts:
            job.status = "pending"
            job.error = "stale running job; retrying"
            job.finished_at = None
        else:
            job.status = "failed"
            job.error = "stale running job; max attempts reached"
            job.finished_at = now
    if jobs:
        await db.commit()
        logger.warning("Recovered %s stale embedding job(s)", len(jobs))
    return len(jobs)


async def process_pending_jobs(limit: int = 1) -> int:
    """Worker entrypoint: claim và xử lý tối đa `limit` job."""
    job_ids: list[str] = []
    async with SessionLocal() as db:
        await recover_stale_jobs(db)
        for _ in range(limit):
            job = await claim_next_job(db)
            if job is None:
                break
            job_ids.append(job.id)

    # Xử lý ngoài session claim để không giữ connection trong lúc ingest lâu.
    for job_id in job_ids:
        await process_job(job_id)
    return len(job_ids)
