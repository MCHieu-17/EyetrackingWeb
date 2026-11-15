from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.auth import User
from app.schemas.aoi import (
    AoiCollectionOut,
    AoiGenerateIn,
    AoiRebuildIn,
    AoiRebuildOut,
    AoiSaveIn,
    AoiUiGenerateIn,
)
from app.services import analysis, aoi
from app.services.aoi.access import slide_with_course

router = APIRouter(tags=["aoi"])


@router.get("/api/aois", response_model=list[AoiCollectionOut])
async def list_aois(
    slide_id: str | None = Query(default=None, alias="slideId"),
    ui_schema: str | None = Query(default=None, alias="uiSchema"),
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    return await aoi.list_aoi_collections(
        db, user, slide_id=slide_id, ui_schema=ui_schema
    )


async def _mark_slide_changed(db: AsyncSession, slide_id: str) -> None:
    _, lesson, _ = await slide_with_course(db, slide_id)
    await analysis.enqueue_lesson_views(db, lesson.id)


@router.post(
    "/api/aois/slides/{slide_id}/generate",
    response_model=AoiCollectionOut,
)
async def generate_slide_aois(
    slide_id: str,
    body: AoiGenerateIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await aoi.generate_slide_aois(db, user, slide_id, body)
    await _mark_slide_changed(db, slide_id)
    await db.commit()
    return result


@router.put(
    "/api/aois/slides/{slide_id}",
    response_model=AoiCollectionOut,
)
async def save_slide_aois(
    slide_id: str,
    body: AoiSaveIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await aoi.save_slide_aois(db, user, slide_id, body)
    await _mark_slide_changed(db, slide_id)
    await db.commit()
    return result


@router.post(
    "/api/aois/ui/{ui_schema}/generate",
    response_model=AoiCollectionOut,
)
async def generate_ui_aois(
    ui_schema: str,
    body: AoiUiGenerateIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await aoi.generate_ui_aois(db, user, ui_schema, body)
    await analysis.mark_ui_changed(db)
    await db.commit()
    return result


@router.put(
    "/api/aois/ui/{ui_schema}",
    response_model=AoiCollectionOut,
)
async def save_ui_aois(
    ui_schema: str,
    body: AoiSaveIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await aoi.save_ui_aois(db, user, ui_schema, body)
    await analysis.mark_ui_changed(db)
    await db.commit()
    return result


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
    await db.commit()
    return AoiRebuildOut(ok=True, runs=runs, completed=completed, failed=failed)
