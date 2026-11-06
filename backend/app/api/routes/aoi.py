from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.aoi import AnalysisRun
from app.models.auth import User
from app.schemas.aoi import (
    AnalysisRunCreateIn,
    AnalysisRunOut,
    AnalysisRunResultOut,
    AoiRebuildIn,
    AoiRebuildOut,
    AoiSetCreateIn,
    AoiSetOut,
    AoiSetPublishOut,
    AoiSetUpdateIn,
)
from app.services import analysis, aoi

router = APIRouter(tags=["aoi"])


@router.get("/api/aoi-sets", response_model=list[AoiSetOut])
async def list_aoi_sets(
    scope: str | None = Query(default=None, pattern="^(slide|ui)$"),
    slide_version_id: str | None = Query(default=None, alias="slideVersionId"),
    ui_schema_version: str | None = Query(default=None, alias="uiSchemaVersion"),
    state: str | None = Query(default=None, pattern="^(draft|published|archived)$"),
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    return await aoi.list_aoi_sets(
        db,
        user,
        scope=scope,
        slide_version_id=slide_version_id,
        ui_schema_version=ui_schema_version,
        state=state,
    )


@router.post("/api/aoi-sets", response_model=AoiSetOut, status_code=201)
async def create_aoi_set(
    body: AoiSetCreateIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    return await aoi.create_aoi_set(db, user, body)


@router.get("/api/aoi-sets/{set_id}", response_model=AoiSetOut)
async def get_aoi_set(
    set_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    row = await aoi.get_aoi_set(db, set_id)
    if row.scope == "slide" and row.slide_version_id:
        await aoi._require_slide_access(db, user, row.slide_version_id)
    return await aoi.get_aoi_set_out(db, set_id)


@router.patch("/api/aoi-sets/{set_id}", response_model=AoiSetOut)
async def update_aoi_set(
    set_id: str,
    body: AoiSetUpdateIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    return await aoi.update_aoi_set(db, user, set_id, body)


@router.post("/api/aoi-sets/{set_id}/publish", response_model=AoiSetPublishOut)
async def publish_aoi_set(
    set_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    row = await aoi.publish_aoi_set(db, user, set_id)
    return AoiSetPublishOut(ok=True, id=row.id, state=row.state)


@router.post("/api/analysis-runs", response_model=AnalysisRunResultOut, status_code=201)
async def create_analysis_run(
    body: AnalysisRunCreateIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    if idempotency_key:
        existing = (
            await db.execute(
                select(AnalysisRun).where(
                    AnalysisRun.session_id == body.session_id,
                    AnalysisRun.aoi_set_id == body.aoi_set_id,
                    AnalysisRun.from_time == body.from_time,
                    AnalysisRun.to_time == body.to_time,
                    AnalysisRun.config["idempotencyKey"].astext == idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return await analysis.get_run_result(db, existing.id)
        body.config = {**body.config, "idempotencyKey": idempotency_key}
    run = await analysis.create_run(db, user, body)
    return await analysis.execute_run(db, run.id)


@router.get("/api/analysis-runs", response_model=list[AnalysisRunOut])
async def list_analysis_runs(
    session_id: str | None = Query(default=None, alias="sessionId"),
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    return await analysis.list_runs(db, user, session_id=session_id)


@router.get("/api/analysis-runs/{run_id}", response_model=AnalysisRunResultOut)
async def get_analysis_run(
    run_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    run = await db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy analysis run")
    _, course, _ = await analysis._session_course(db, run.session_id)
    from app.api.deps import can_access_course

    if not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    return await analysis.get_run_result(db, run_id)


@router.get("/api/analysis-runs/{run_id}/export")
async def export_analysis_run(
    run_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    run = await db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy analysis run")
    _, course, _ = await analysis._session_course(db, run.session_id)
    from app.api.deps import can_access_course

    if not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    return StreamingResponse(
        analysis.export_lines(run_id),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": f'attachment; filename="analysis-{run_id}.jsonl"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/api/aoi/rebuild", response_model=AoiRebuildOut)
async def rebuild_aoi(
    body: AoiRebuildIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    runs, completed, failed = await analysis.rebuild_course(
        db,
        user,
        course_id=body.course_id,
        from_time=body.from_time,
        to_time=body.to_time,
        algorithm_version=body.algorithm_version,
    )
    return AoiRebuildOut(ok=True, runs=runs, completed=completed, failed=failed)
