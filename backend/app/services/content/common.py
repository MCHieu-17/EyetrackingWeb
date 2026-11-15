"""Shared helpers for the simplified content service."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course, CourseModule, Lesson

logger = logging.getLogger("app.services.content")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _not_found(message: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=message)


async def get_course_or_404(db: AsyncSession, course_id: str) -> Course:
    course = await db.get(Course, course_id)
    if course is None:
        raise _not_found("Không tìm thấy khóa học")
    return course


async def course_of_module(
    db: AsyncSession, module_id: str
) -> tuple[Course, CourseModule]:
    module = await db.get(CourseModule, module_id)
    if module is None:
        raise _not_found("Không tìm thấy chương")
    course = await db.get(Course, module.course_id)
    if course is None:
        raise _not_found("Không tìm thấy khóa học")
    return course, module


async def course_of_lesson(db: AsyncSession, lesson_id: str) -> tuple[Course, Lesson]:
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise _not_found("Không tìm thấy bài học")
    module = await db.get(CourseModule, lesson.module_id)
    if module is None:
        raise _not_found("Không tìm thấy chương")
    course = await db.get(Course, module.course_id)
    if course is None:
        raise _not_found("Không tìm thấy khóa học")
    return course, lesson


def touch_course(course: Course) -> None:
    course.updated_at = _now()


def touch_lesson(lesson: Lesson) -> None:
    lesson.updated_at = _now()
