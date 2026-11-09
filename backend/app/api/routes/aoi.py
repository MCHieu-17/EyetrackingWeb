from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.auth import User
from app.schemas.aoi import (
    AoiRebuildIn,
    AoiRebuildOut,
    AoiSetGenerateIn,
    AoiSetOut,
    AoiSetSaveIn,
    AoiUiGenerateIn,
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


@router.post(
    "/api/aoi-sets/slide/{slide_version_id}/generate",
    response_model=AoiSetOut,
)
async def generate_slide_aoi_set(
    slide_version_id: str,
    body: AoiSetGenerateIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    return await aoi.generate_slide_aoi_set(db, user, slide_version_id, body)


@router.put(
    "/api/aoi-sets/slide/{slide_version_id}",
    response_model=AoiSetOut,
)
async def save_slide_aoi_set(
    slide_version_id: str,
    body: AoiSetSaveIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    return await aoi.save_slide_aoi_set(db, user, slide_version_id, body)


@router.post(
    "/api/aoi-sets/ui/{ui_schema_version}/generate",
    response_model=AoiSetOut,
)
async def generate_ui_aoi_set(
    ui_schema_version: str,
    body: AoiUiGenerateIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    return await aoi.generate_ui_aoi_set(db, user, ui_schema_version, body)


@router.put(
    "/api/aoi-sets/ui/{ui_schema_version}",
    response_model=AoiSetOut,
)
async def save_ui_aoi_set(
    ui_schema_version: str,
    body: AoiSetSaveIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    return await aoi.save_ui_aoi_set(db, user, ui_schema_version, body)


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
        lesson_id=body.lesson_id,
        from_time=body.from_time,
        to_time=body.to_time,
        algorithm_version=body.algorithm_version,
    )
    return AoiRebuildOut(ok=True, runs=runs, completed=completed, failed=failed)
