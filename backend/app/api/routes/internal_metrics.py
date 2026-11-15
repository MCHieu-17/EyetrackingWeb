"""Metrics nội bộ cho load test/ops."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import get_redis
from app.db.session import engine, get_db
from app.models.background_job import BackgroundJob

router = APIRouter(tags=["internal"])


async def _count(
    db: AsyncSession, kind: str, statuses: tuple[str, ...]
) -> int:
    return int(
        (
            await db.execute(
                select(func.count())
                .select_from(BackgroundJob)
                .where(
                    BackgroundJob.kind == kind,
                    BackgroundJob.status.in_(statuses),
                )
            )
        ).scalar_one()
    )


@router.get("/internal/metrics")
async def metrics(db: AsyncSession = Depends(get_db)):
    pool = engine.pool
    redis_ok = False
    client = await get_redis()
    if client is not None:
        try:
            redis_ok = bool(await client.ping())
        except Exception:  # noqa: BLE001
            redis_ok = False

    return {
        "db_pool": {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        },
        "redis": {"ok": redis_ok},
        "queues": {
            "analysis_pending": await _count(
                db, "analyze_lesson", ("queued", "processing")
            ),
            "embedding_pending": await _count(
                db, "index_slides", ("queued", "processing")
            ),
            "slide_import_queued": await _count(
                db, "import_slides", ("queued", "processing")
            ),
        },
    }
