"""Course module CRUD."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload, selectinload

from app.models.auth import User
from app.models.course import Course, CourseVersion, CourseVersionModule
from app.services.content.common import (
    _not_found,
    bump_generation,
    get_draft_version,
)


async def course_of_module(
    db: AsyncSession, module_id: str
) -> tuple[Course, CourseVersionModule]:
    module = await db.get(
        CourseVersionModule,
        module_id,
        options=[raiseload(CourseVersionModule.items)],
    )
    if module is None:
        raise _not_found("Không tìm thấy chương")
    version = await db.get(
        CourseVersion,
        module.course_version_id,
        options=[
            raiseload(CourseVersion.modules),
            raiseload(CourseVersion.items),
        ],
    )
    if version is None:
        raise _not_found("Không tìm thấy phiên bản khóa học")
    course = await db.get(
        Course,
        version.course_id,
        options=[
            raiseload(Course.versions),
            raiseload(Course.enrollments),
            raiseload(Course.owner),
            raiseload(Course.creator),
        ],
    )
    if course is None:
        raise _not_found("Không tìm thấy khóa học")
    return course, module


async def _draft_module(
    db: AsyncSession, course: Course, module_id: str, user: User
) -> tuple[CourseVersion, CourseVersionModule]:
    draft = await get_draft_version(db, course, user)
    assert draft is not None
    # delete_module dựa vào cascade delete-orphan nên phải tải items trước.
    module = await db.get(
        CourseVersionModule,
        module_id,
        options=[selectinload(CourseVersionModule.items)],
    )
    if module is None or module.course_version_id != draft.id:
        raise _not_found("Không tìm thấy chương trong bản nháp")
    return draft, module


async def _next_module_position(db: AsyncSession, course_version_id: str) -> int:
    value = (
        await db.execute(
            select(func.coalesce(func.max(CourseVersionModule.position), -1) + 1).where(
                CourseVersionModule.course_version_id == course_version_id
            )
        )
    ).scalar_one()
    return int(value)


async def create_module(
    db: AsyncSession, course: Course, user: User, title: str
) -> CourseVersionModule:
    draft = await get_draft_version(db, course, user)
    assert draft is not None
    module = CourseVersionModule(
        course_version_id=draft.id,
        title=title,
        position=await _next_module_position(db, draft.id),
    )
    db.add(module)
    bump_generation(draft)
    await db.flush()
    return module


async def update_module(
    db: AsyncSession, course: Course, user: User, module_id: str, title: str
) -> CourseVersionModule:
    draft, module = await _draft_module(db, course, module_id, user)
    module.title = title
    bump_generation(draft)
    await db.flush()
    return module


async def delete_module(
    db: AsyncSession, course: Course, user: User, module_id: str
) -> None:
    draft, module = await _draft_module(db, course, module_id, user)
    await db.delete(module)
    bump_generation(draft)
    await db.flush()
