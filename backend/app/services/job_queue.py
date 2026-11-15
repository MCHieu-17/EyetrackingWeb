"""Cơ chế claim/recover dùng chung cho `background_jobs`.

Payload và cách xử lý từng loại job vẫn nằm ở service riêng. Module này chỉ
chuẩn hoá vòng đời claim, stale recovery và retry để ba worker không lệch nhau.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.background_job import BackgroundJob

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def recover_stale_jobs(
    db: AsyncSession, *, kind: str, stale_seconds: int
) -> int:
    """Đưa job ``processing`` quá hạn về queued hoặc failed theo số attempts."""
    if stale_seconds <= 0:
        return 0
    cutoff = _now() - timedelta(seconds=stale_seconds)
    jobs = (
        (
            await db.execute(
                select(BackgroundJob)
                .where(
                    BackgroundJob.kind == kind,
                    BackgroundJob.status == "processing",
                    BackgroundJob.started_at < cutoff,
                )
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    if not jobs:
        return 0

    now = _now()
    for job in jobs:
        job.updated_at = now
        if job.attempts < job.max_attempts:
            job.status = "queued"
            job.started_at = None
            job.finished_at = None
            job.error = "stale running job; retrying"
        else:
            job.status = "failed"
            job.finished_at = now
            job.error = "stale running job; max attempts reached"
    await db.commit()
    logger.warning("recovered %s stale %s job(s)", len(jobs), kind)
    return len(jobs)


async def claim_next_jobs(
    db: AsyncSession, *, kind: str, limit: int = 1
) -> list[BackgroundJob]:
    """Claim tối đa ``limit`` job queued, khoá bằng ``SKIP LOCKED``."""
    if limit <= 0:
        return []
    jobs = (
        (
            await db.execute(
                select(BackgroundJob)
                .where(
                    BackgroundJob.kind == kind,
                    BackgroundJob.status == "queued",
                )
                .order_by(BackgroundJob.created_at)
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    if not jobs:
        return []

    now = _now()
    for job in jobs:
        job.status = "processing"
        job.started_at = now
        job.attempts += 1
        job.updated_at = now
    await db.commit()
    return list(jobs)
