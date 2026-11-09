"""Execute analysis runs và worker entrypoint."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload

from app.db.session import SessionLocal
from app.models.aoi import AnalysisRun, AoiHit, AoiSet, PresentationMetric
from app.models.gaze import ContentPresentation, LearningSession
from app.schemas.aoi import AnalysisRunResultOut, PresentationMetricOut
from app.services import metrics
from app.services.analysis.common import _now, _run_out, _watermark
from app.services.analysis.hits import _insert_slide_hits, _insert_ui_hits


async def execute_run(db: AsyncSession, run_id: str) -> AnalysisRunResultOut:
    run = await db.get(
        AnalysisRun,
        run_id,
        options=[raiseload(AnalysisRun.aoi_set)],
    )
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy analysis run")
    if run.status == "completed":
        return await get_run_result(db, run.id)
    run.status = "running"
    run.error = None
    await db.commit()

    try:
        aoi_set = await db.get(
            AoiSet,
            run.aoi_set_id,
            options=[raiseload(AoiSet.definitions)],
        )
        if aoi_set is None:
            raise RuntimeError("AOI set không còn tồn tại")
        watermark = await _watermark(db, run.session_id, run.presentation_id)
        watermark_no = watermark.batch_no if watermark else None

        await db.execute(
            text("DELETE FROM aoi_hits WHERE run_id = :run_id"), {"run_id": run.id}
        )
        if aoi_set.scope == "slide":
            inserted = await _insert_slide_hits(db, run, watermark_no)
        else:
            inserted = await _insert_ui_hits(db, run, watermark_no)

        if run.presentation_id:
            await metrics.compute_presentation_metrics(
                db,
                presentation_id=run.presentation_id,
                algorithm_version=run.algorithm_version,
                from_time=run.from_time,
                to_time=run.to_time,
                batch_watermark=run.batch_watermark,
            )
        else:
            await metrics.refresh_session_metrics(
                db,
                session_id=run.session_id,
                from_time=run.from_time,
                to_time=run.to_time,
                algorithm_version=run.algorithm_version,
                batch_watermark=run.batch_watermark,
            )
        run.status = "completed"
        run.completed_at = _now()
        await db.commit()
        await db.refresh(run)
        result = await get_run_result(db, run.id)
        result.hit_count = inserted
        return result
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        run = await db.get(
            AnalysisRun,
            run_id,
            options=[raiseload(AnalysisRun.aoi_set)],
        )
        if run is not None:
            run.status = "failed"
            run.error = str(exc)[:1000]
            await db.commit()
        raise


async def get_run_result(db: AsyncSession, run_id: str) -> AnalysisRunResultOut:
    run = await db.get(
        AnalysisRun,
        run_id,
        options=[raiseload(AnalysisRun.aoi_set)],
    )
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy analysis run")
    hit_count = int(
        (
            await db.execute(
                select(func.count()).select_from(AoiHit).where(AoiHit.run_id == run.id)
            )
        ).scalar_one()
    )
    metric_rows = (
        await db.execute(
            select(PresentationMetric)
            .join(
                ContentPresentation,
                ContentPresentation.id == PresentationMetric.presentation_id,
            )
            .where(
                ContentPresentation.session_id == run.session_id,
                PresentationMetric.algorithm_version == run.algorithm_version,
            )
            .order_by(PresentationMetric.computed_at)
        )
    ).scalars().all()
    return AnalysisRunResultOut(
        run=_run_out(run),
        hit_count=hit_count,
        metrics=[
            PresentationMetricOut(
                presentation_id=row.presentation_id,
                algorithm_version=row.algorithm_version,
                batch_watermark=row.batch_watermark,
                sample_count=row.sample_count,
                on_slide_count=row.on_slide_count,
                dwell_ms=row.dwell_ms,
                fixation_count=row.fixation_count,
                heatmap_grid=row.heatmap_grid,
                computed_at=row.computed_at,
            )
            for row in metric_rows
        ],
    )


async def _create_run(
    db: AsyncSession,
    *,
    session: LearningSession,
    presentation: ContentPresentation,
    aoi_set_id: str,
    start: datetime,
    end: datetime,
    algorithm_version: str,
    watermark_id: str | None,
    duplicate: bool,
) -> AnalysisRun | None:
    if duplicate:
        return None
    run = AnalysisRun(
        session_id=session.id,
        presentation_id=presentation.id,
        aoi_set_id=aoi_set_id,
        from_time=start,
        to_time=end,
        batch_watermark=watermark_id,
        algorithm_version=algorithm_version,
        config={},
        status="pending",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def execute_pending_runs(limit: int = 10) -> int:
    """Worker entrypoint: chạy các run pending theo thứ tự tạo.

    Mỗi vòng chỉ khóa đúng một run. `execute_run` chuyển status sang running
    và commit, giải phóng lock trước khi vòng sau chọn run kế tiếp — tránh
    việc commit của run đầu giải phóng lock của cả loạt run đã chọn.
    """
    processed = 0
    async with SessionLocal() as db:
        for _ in range(limit):
            run_id = (
                await db.execute(
                    select(AnalysisRun.id)
                    .where(AnalysisRun.status == "pending")
                    .order_by(AnalysisRun.created_at)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if run_id is None:
                break
            try:
                await execute_run(db, run_id)
            except Exception:  # noqa: BLE001
                pass
            processed += 1
        return processed
