"""Course module CRUD."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.course import Course, CourseModule
from app.services.content.common import (
    _not_found,
    _now,
    course_of_module,
    touch_course,
)

__all__ = ["course_of_module"]


async def create_module(
    db: AsyncSession, course: Course, user: User, title: str
) -> CourseModule:
    position = (
        await db.execute(
            select(func.coalesce(func.max(CourseModule.position), -1) + 1).where(
                CourseModule.course_id == course.id
            )
        )
    ).scalar_one()
    module = CourseModule(course_id=course.id, title=title, position=int(position))
    db.add(module)
    touch_course(course)
    await db.flush()
    return module


async def update_module(
    db: AsyncSession, course: Course, user: User, module_id: str, title: str
) -> CourseModule:
    module = await db.get(CourseModule, module_id)
    if module is None or module.course_id != course.id:
        raise _not_found("Không tìm thấy chương")
    module.title = title
    module.updated_at = _now()
    touch_course(course)
    await db.flush()
    return module


async def delete_module(
    db: AsyncSession, course: Course, user: User, module_id: str
) -> None:
    module = await db.get(CourseModule, module_id)
    if module is None or module.course_id != course.id:
        raise _not_found("Không tìm thấy chương")
    await db.delete(module)
    touch_course(course)
    await db.flush()
