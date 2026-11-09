"""Metrics nội bộ cho load test/ops.

Chỉ nên gọi trực tiếp backend (localhost:8001) hoặc trong Docker network;
nginx đã chặn `/internal/` từ bên ngoài.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import get_redis
from app.db.session import engine, get_db
from app.models.aoi import AnalysisRun
from app.models.embedding_job import EmbeddingJob
from app.models.media import SlideImportJob

router = APIRouter(tags=["internal"])


async def _count(db: AsyncSession, model, status: str) -> int:
    return int(
        (
            await db.execute(
                select(func.count())
                .select_from(model)
                .where(model.status == status)
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
            "analysis_pending": await _count(db, AnalysisRun, "pending"),
            "analysis_running": await _count(db, AnalysisRun, "running"),
            "embedding_pending": await _count(db, EmbeddingJob, "pending"),
            "embedding_running": await _count(db, EmbeddingJob, "running"),
            "slide_import_queued": await _count(db, SlideImportJob, "queued"),
            "slide_import_processing": await _count(
                db, SlideImportJob, "processing"
            ),
        },
    }
