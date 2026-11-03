from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.aoi import AoiDefinition, AoiLayoutRect, AoiLayoutSnapshot
from app.models.auth import User
from app.models.course import Enrollment
from app.models.gaze import LearningSession
from app.schemas.aoi import (
    AoiDefinitionIn,
    AoiDefinitionOut,
    AoiDefinitionUpdate,
    AoiLayoutSnapshotIn,
    AoiLayoutSnapshotOut,
    AoiRebuildIn,
    AoiRebuildOut,
)
from app.services import aoi_hits

router = APIRouter(tags=["aoi"])


def _definition_out(row: AoiDefinition) -> AoiDefinitionOut:
    return AoiDefinitionOut(
        id=row.id,
        code=row.code,
        name=row.name,
        description=row.description,
        scope=row.scope,
        parent_id=row.parent_id,
        selector=row.selector,
        lesson_content_id=row.lesson_content_id,
        is_active=row.is_active,
        metadata=row.metadata_ or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/api/aoi-definitions", response_model=list[AoiDefinitionOut])
async def list_aoi_definitions(
    include_inactive: bool = False,
    _: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AoiDefinition).order_by(AoiDefinition.code)
    if not include_inactive:
        stmt = stmt.where(AoiDefinition.is_active.is_(True))
    rows = (await db.execute(stmt)).scalars().all()
    return [_definition_out(row) for row in rows]


@router.post(
    "/api/aoi-definitions",
    response_model=AoiDefinitionOut,
    status_code=201,
)
async def create_aoi_definition(
    body: AoiDefinitionIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    if body.parent_id:
        parent = await db.get(AoiDefinition, body.parent_id)
        if parent is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Không tìm thấy AOI cha"
            )

    row = AoiDefinition(
        code=body.code.strip(),
        name=body.name.strip(),
        description=body.description,
        scope=body.scope,
        parent_id=body.parent_id,
        selector=body.selector,
        lesson_content_id=body.lesson_content_id,
        is_active=body.is_active,
        metadata_=body.metadata,
        created_by=user.id,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Mã AOI đã tồn tại (hoặc đang active)",
        )
    await db.refresh(row)
    return _definition_out(row)


@router.patch("/api/aoi-definitions/{aoi_id}", response_model=AoiDefinitionOut)
async def update_aoi_definition(
    aoi_id: str,
    body: AoiDefinitionUpdate,
    _: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(AoiDefinition, aoi_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy AOI")

    if body.parent_id is not None:
        if body.parent_id == aoi_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="AOI không thể là cha của chính nó",
            )
        parent = await db.get(AoiDefinition, body.parent_id)
        if parent is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Không tìm thấy AOI cha"
            )
        row.parent_id = body.parent_id
    if body.name is not None:
        row.name = body.name.strip()
    if body.description is not None:
        row.description = body.description
    if body.selector is not None:
        row.selector = body.selector
    if body.is_active is not None:
        row.is_active = body.is_active
    if body.metadata is not None:
        row.metadata_ = body.metadata

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Mã AOI đã tồn tại (hoặc đang active)",
        )
    await db.refresh(row)
    return _definition_out(row)


@router.delete("/api/aoi-definitions/{aoi_id}", response_model=dict)
async def delete_aoi_definition(
    aoi_id: str,
    _: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(AoiDefinition, aoi_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy AOI")
    # Soft delete: giữ lịch sử hits và cho phép bật lại sau này.
    row.is_active = False
    await db.commit()
    return {"ok": True}


@router.post(
    "/api/learning-sessions/{session_id}/aoi-layout",
    response_model=AoiLayoutSnapshotOut,
    status_code=201,
)
async def create_aoi_layout_snapshot(
    session_id: str,
    body: AoiLayoutSnapshotIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(LearningSession, session_id)
    if session is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên học"
        )
    enrollment = await db.get(Enrollment, session.enrollment_id)
    if enrollment is None or enrollment.student_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")

    if (
        session.calibration_width_px is None
        or session.calibration_height_px is None
        or body.viewport_width_px != session.calibration_width_px
        or body.viewport_height_px != session.calibration_height_px
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "viewport_mismatch",
                "message": "Viewport hiện tại khác lúc hiệu chỉnh.",
            },
        )

    snapshot = AoiLayoutSnapshot(
        learning_session_id=session.id,
        viewport_width_px=body.viewport_width_px,
        viewport_height_px=body.viewport_height_px,
        layout_key=body.layout_key,
    )
    db.add(snapshot)
    await db.flush()

    for rect in body.rects:
        db.add(
            AoiLayoutRect(
                snapshot_id=snapshot.id,
                aoi_code=rect.code.strip(),
                x_min=rect.x_min,
                y_min=rect.y_min,
                x_max=rect.x_max,
                y_max=rect.y_max,
            )
        )

    await db.commit()
    await db.refresh(snapshot)
    return AoiLayoutSnapshotOut(id=snapshot.id, captured_at=snapshot.captured_at)


@router.post("/api/aoi/rebuild", response_model=AoiRebuildOut)
async def rebuild_aoi(
    body: AoiRebuildIn,
    _: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    inserted = await aoi_hits.rebuild_aoi_hits(
        db,
        session_id=body.session_id,
        lesson_id=body.lesson_id,
        course_id=body.course_id,
        from_time=body.from_time,
        to_time=body.to_time,
    )
    return AoiRebuildOut(ok=True, inserted=inserted)
