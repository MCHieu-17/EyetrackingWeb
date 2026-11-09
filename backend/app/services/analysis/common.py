"""Shared helpers cho analysis package."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aoi import AnalysisRun, AoiDefinition
from app.models.gaze import GazeBatch
from app.schemas.aoi import AnalysisRunOut

NO_LABEL_CODE = "no_label"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _run_out(row: AnalysisRun) -> AnalysisRunOut:
    return AnalysisRunOut(
        id=row.id,
        session_id=row.session_id,
        presentation_id=row.presentation_id,
        aoi_set_id=row.aoi_set_id,
        from_time=row.from_time,
        to_time=row.to_time,
        batch_watermark=row.batch_watermark,
        algorithm_version=row.algorithm_version,
        status=row.status,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


async def _watermark(
    db: AsyncSession, session_id: str, presentation_id: str | None = None
) -> GazeBatch | None:
    stmt = select(GazeBatch).where(GazeBatch.session_id == session_id)
    if presentation_id:
        stmt = stmt.where(GazeBatch.presentation_id == presentation_id)
    return (
        await db.execute(stmt.order_by(GazeBatch.batch_no.desc()).limit(1))
    ).scalar_one_or_none()


def _filters(
    run: AnalysisRun,
    watermark_no: int | None,
    *,
    alias: str = "gs",
    batch_alias: str = "gb",
) -> tuple[str, dict]:
    conditions = [
        f"{alias}.session_id = :session_id",
        f"{alias}.event_time >= :from_time",
        f"{alias}.event_time < :to_time",
        f"{alias}.status = 'ok'",
        f"{alias}.viewport_x IS NOT NULL",
        f"{alias}.viewport_y IS NOT NULL",
    ]
    params: dict = {
        "session_id": run.session_id,
        "from_time": run.from_time,
        "to_time": run.to_time,
        "aoi_set_id": run.aoi_set_id,
        "run_id": run.id,
    }
    if run.presentation_id:
        conditions.append(f"{batch_alias}.presentation_id = :presentation_id")
        params["presentation_id"] = run.presentation_id
    if watermark_no is not None:
        conditions.append(f"{batch_alias}.batch_no <= :watermark_no")
        params["watermark_no"] = watermark_no
    return " AND ".join(conditions), params


async def _no_label_id(db: AsyncSession, set_id: str) -> str | None:
    return (
        await db.execute(
            select(AoiDefinition.id).where(
                AoiDefinition.aoi_set_id == set_id,
                AoiDefinition.code == NO_LABEL_CODE,
            )
        )
    ).scalar_one_or_none()
