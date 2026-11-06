"""AOI sets: draft/published, slide/UI scope, immutable published revisions."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import can_access_course
from app.models.aoi import AoiDefinition, AoiSet
from app.models.auth import User
from app.models.course import Course, Lesson, Slide, SlideVersion
from app.schemas.aoi import (
    AoiDefinitionIn,
    AoiDefinitionOut,
    AoiSetCreateIn,
    AoiSetOut,
    AoiSetUpdateIn,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _not_found(message: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=message)


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail=message)


def _definition_out(row: AoiDefinition) -> AoiDefinitionOut:
    return AoiDefinitionOut(
        id=row.id,
        code=row.code,
        name=row.name,
        parent_id=row.parent_id,
        geometry=row.geometry or {},
    )


def _set_out(row: AoiSet, definitions: list[AoiDefinition]) -> AoiSetOut:
    return AoiSetOut(
        id=row.id,
        scope=row.scope,
        slide_version_id=row.slide_version_id,
        ui_schema_version=row.ui_schema_version,
        revision=row.revision,
        state=row.state,
        created_by=row.created_by,
        created_at=row.created_at,
        published_at=row.published_at,
        definitions=[_definition_out(item) for item in definitions],
    )


def _validate_geometry(scope: str, geometry: dict) -> None:
    if not isinstance(geometry, dict):
        raise _bad_request("geometry phải là object")
    if scope == "slide":
        keys = ("xMin", "yMin", "xMax", "yMax")
        if not all(key in geometry for key in keys):
            raise _bad_request("AOI slide cần xMin/yMin/xMax/yMax")
        try:
            x_min = float(geometry["xMin"])
            y_min = float(geometry["yMin"])
            x_max = float(geometry["xMax"])
            y_max = float(geometry["yMax"])
        except (TypeError, ValueError) as exc:
            raise _bad_request("Toạ độ AOI phải là số") from exc
        if not (0.0 <= x_min < x_max <= 1.0 and 0.0 <= y_min < y_max <= 1.0):
            raise _bad_request("Toạ độ AOI phải trong [0,1] và min < max")
    else:
        selector = geometry.get("selector")
        if selector is not None and not isinstance(selector, str):
            raise _bad_request("selector phải là chuỗi")
        if selector is None and not all(
            key in geometry for key in ("xMin", "yMin", "xMax", "yMax")
        ):
            raise _bad_request("AOI UI cần selector hoặc rect")


async def _slide_version_course(
    db: AsyncSession, slide_version_id: str
) -> tuple[SlideVersion, Slide, Lesson, Course]:
    slide_version = await db.get(SlideVersion, slide_version_id)
    if slide_version is None:
        raise _not_found("Không tìm thấy phiên bản slide")
    slide = await db.get(Slide, slide_version.slide_id)
    lesson = await db.get(Lesson, slide.lesson_id) if slide else None
    course = await db.get(Course, lesson.course_id) if lesson else None
    if slide is None or lesson is None or course is None:
        raise _not_found("Không tìm thấy khóa học của slide")
    return slide_version, slide, lesson, course


async def _require_slide_access(
    db: AsyncSession, user: User, slide_version_id: str
) -> None:
    _, _, _, course = await _slide_version_course(db, slide_version_id)
    if not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")


async def _definitions(db: AsyncSession, set_id: str) -> list[AoiDefinition]:
    return list(
        (
            await db.execute(
                select(AoiDefinition)
                .where(AoiDefinition.aoi_set_id == set_id)
                .order_by(AoiDefinition.code)
            )
        )
        .scalars()
        .all()
    )


async def get_aoi_set(db: AsyncSession, set_id: str) -> AoiSet:
    row = await db.get(AoiSet, set_id)
    if row is None:
        raise _not_found("Không tìm thấy bộ AOI")
    return row


async def get_aoi_set_out(db: AsyncSession, set_id: str) -> AoiSetOut:
    row = await get_aoi_set(db, set_id)
    return _set_out(row, await _definitions(db, row.id))


async def list_aoi_sets(
    db: AsyncSession,
    user: User,
    *,
    scope: str | None = None,
    slide_version_id: str | None = None,
    ui_schema_version: str | None = None,
    state: str | None = None,
) -> list[AoiSetOut]:
    stmt = select(AoiSet).order_by(AoiSet.created_at.desc())
    if scope:
        stmt = stmt.where(AoiSet.scope == scope)
    if slide_version_id:
        stmt = stmt.where(AoiSet.slide_version_id == slide_version_id)
    if ui_schema_version:
        stmt = stmt.where(AoiSet.ui_schema_version == ui_schema_version)
    if state:
        stmt = stmt.where(AoiSet.state == state)
    rows = list((await db.execute(stmt)).scalars().all())
    out: list[AoiSetOut] = []
    for row in rows:
        if row.scope == "slide" and row.slide_version_id:
            try:
                await _require_slide_access(db, user, row.slide_version_id)
            except HTTPException:
                continue
        out.append(_set_out(row, await _definitions(db, row.id)))
    return out


async def _next_revision(
    db: AsyncSession,
    *,
    scope: str,
    slide_version_id: str | None,
    ui_schema_version: str | None,
) -> int:
    stmt = select(func.coalesce(func.max(AoiSet.revision), 0)).where(
        AoiSet.scope == scope
    )
    if scope == "slide":
        stmt = stmt.where(AoiSet.slide_version_id == slide_version_id)
    else:
        stmt = stmt.where(AoiSet.ui_schema_version == ui_schema_version)
    return int((await db.execute(stmt)).scalar_one()) + 1


async def _insert_definitions(
    db: AsyncSession, set_id: str, definitions: list[AoiDefinitionIn], scope: str
) -> None:
    by_code: dict[str, AoiDefinition] = {}
    for item in definitions:
        _validate_geometry(scope, item.geometry)
        if item.code in by_code:
            raise _bad_request(f"Mã AOI bị trùng: {item.code}")
        parent_id = item.parent_id
        if parent_id and parent_id in by_code:
            parent_id = by_code[parent_id].id
        row = AoiDefinition(
            aoi_set_id=set_id,
            code=item.code,
            name=item.name,
            parent_id=parent_id,
            geometry=item.geometry,
        )
        db.add(row)
        await db.flush()
        by_code[item.code] = row
    for item in definitions:
        if item.parent_id and item.parent_id not in by_code:
            parent = await db.get(AoiDefinition, item.parent_id)
            if parent is None or parent.aoi_set_id != set_id:
                raise _bad_request("AOI cha phải thuộc cùng bộ AOI")


async def create_aoi_set(
    db: AsyncSession, user: User, body: AoiSetCreateIn
) -> AoiSetOut:
    if body.scope == "slide" and body.slide_version_id:
        await _require_slide_access(db, user, body.slide_version_id)
    revision = await _next_revision(
        db,
        scope=body.scope,
        slide_version_id=body.slide_version_id,
        ui_schema_version=body.ui_schema_version,
    )
    row = AoiSet(
        scope=body.scope,
        slide_version_id=body.slide_version_id,
        ui_schema_version=body.ui_schema_version,
        revision=revision,
        state="draft",
        created_by=user.id,
    )
    db.add(row)
    await db.flush()
    await _insert_definitions(db, row.id, body.definitions, body.scope)
    await db.commit()
    await db.refresh(row)
    return _set_out(row, await _definitions(db, row.id))


async def update_aoi_set(
    db: AsyncSession, user: User, set_id: str, body: AoiSetUpdateIn
) -> AoiSetOut:
    row = await get_aoi_set(db, set_id)
    if row.scope == "slide" and row.slide_version_id:
        await _require_slide_access(db, user, row.slide_version_id)
    if row.state != "draft":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "aoi_set_immutable", "message": "Bộ AOI đã publish, không sửa trực tiếp"},
        )
    existing = await _definitions(db, row.id)
    for item in existing:
        await db.delete(item)
    await db.flush()
    await _insert_definitions(db, row.id, body.definitions, row.scope)
    await db.commit()
    await db.refresh(row)
    return _set_out(row, await _definitions(db, row.id))


async def publish_aoi_set(db: AsyncSession, user: User, set_id: str) -> AoiSetOut:
    row = await get_aoi_set(db, set_id)
    if row.scope == "slide" and row.slide_version_id:
        await _require_slide_access(db, user, row.slide_version_id)
    if row.state == "published":
        return _set_out(row, await _definitions(db, row.id))
    if row.state != "draft":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "aoi_set_archived", "message": "Bộ AOI đã archive"},
        )
    definitions = await _definitions(db, row.id)
    if not definitions:
        raise _bad_request("Bộ AOI chưa có định nghĩa nào")

    target = (
        AoiSet.slide_version_id == row.slide_version_id
        if row.scope == "slide"
        else AoiSet.ui_schema_version == row.ui_schema_version
    )
    previous = (
        await db.execute(
            select(AoiSet).where(
                AoiSet.scope == row.scope,
                target,
                AoiSet.state == "published",
                AoiSet.id != row.id,
            )
        )
    ).scalars().all()
    for item in previous:
        item.state = "archived"
    await db.flush()

    row.state = "published"
    row.published_at = _now()
    await db.commit()
    await db.refresh(row)
    return _set_out(row, definitions)


async def published_aoi_set(
    db: AsyncSession,
    *,
    slide_version_id: str | None = None,
    ui_schema_version: str | None = None,
) -> AoiSet | None:
    stmt = select(AoiSet).where(AoiSet.state == "published")
    if slide_version_id:
        stmt = stmt.where(AoiSet.slide_version_id == slide_version_id)
    elif ui_schema_version:
        stmt = stmt.where(AoiSet.ui_schema_version == ui_schema_version)
    else:
        return None
    return (await db.execute(stmt)).scalar_one_or_none()


async def resolve_aoi_set_for_session(
    db: AsyncSession, session_id: str
) -> AoiSet | None:
    """UI AOI set published mới nhất (dùng cho layout snapshot)."""
    return await published_aoi_set(db, ui_schema_version="reader-v1")
