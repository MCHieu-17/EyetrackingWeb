"""AOI set access checks and published/latest lookups."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import can_access_course, can_manage_course
from app.models.aoi import AoiSet
from app.models.auth import User
from app.models.course import Course, Lesson, Slide, SlideVersion

from .common import _not_found


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


async def _require_slide_manage(
    db: AsyncSession, user: User, slide_version_id: str
) -> None:
    _, _, _, course = await _slide_version_course(db, slide_version_id)
    if not await can_manage_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")


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


async def _latest_set_for_slide(
    db: AsyncSession, slide_version_id: str
) -> AoiSet | None:
    rows = list(
        (
            await db.execute(
                select(AoiSet)
                .where(
                    AoiSet.scope == "slide",
                    AoiSet.slide_version_id == slide_version_id,
                )
                .order_by(AoiSet.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    draft = next((row for row in rows if row.state == "draft"), None)
    published = next((row for row in rows if row.state == "published"), None)
    return draft or published


async def _latest_set_for_ui(
    db: AsyncSession, ui_schema_version: str
) -> AoiSet | None:
    rows = list(
        (
            await db.execute(
                select(AoiSet)
                .where(
                    AoiSet.scope == "ui",
                    AoiSet.ui_schema_version == ui_schema_version,
                )
                .order_by(AoiSet.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    draft = next((row for row in rows if row.state == "draft"), None)
    published = next((row for row in rows if row.state == "published"), None)
    return draft or published
