"""AOI access helpers."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.course import Course, CourseModule, Lesson, Slide
from app.services.access import can_manage_course

from .common import _not_found


async def slide_with_course(
    db: AsyncSession, slide_id: str
) -> tuple[Slide, Lesson, Course]:
    slide = await db.get(Slide, slide_id)
    if slide is None:
        raise _not_found("Không tìm thấy slide")
    lesson = await db.get(Lesson, slide.lesson_id)
    if lesson is None:
        raise _not_found("Không tìm thấy bài học")
    module = await db.get(CourseModule, lesson.module_id)
    course = await db.get(Course, module.course_id) if module else None
    if course is None:
        raise _not_found("Không tìm thấy khóa học")
    return slide, lesson, course


async def require_slide_manage(
    db: AsyncSession, user: User, slide_id: str
) -> tuple[Slide, Lesson, Course]:
    slide, lesson, course = await slide_with_course(db, slide_id)
    if not await can_manage_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    return slide, lesson, course


async def require_ui_manage(db: AsyncSession, user: User) -> None:
    if user.role not in {"teacher", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
