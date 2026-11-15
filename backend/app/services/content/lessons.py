"""Lesson and quiz item CRUD, ordering."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.course import Course, CourseModule, Lesson
from app.services.content.common import (
    _not_found,
    _now,
    course_of_lesson,
    touch_course,
)


async def _next_lesson_position(db: AsyncSession, module_id: str) -> int:
    value = (
        await db.execute(
            select(func.coalesce(func.max(Lesson.position), -1) + 1).where(
                Lesson.module_id == module_id
            )
        )
    ).scalar_one()
    return int(value)


async def _module_of_course(
    db: AsyncSession, course: Course, module_id: str
) -> CourseModule:
    module = await db.get(CourseModule, module_id)
    if module is None or module.course_id != course.id:
        raise _not_found("Không tìm thấy chương")
    return module


async def create_lesson(
    db: AsyncSession, course: Course, user: User, module_id: str, title: str
) -> Lesson:
    module = await _module_of_course(db, course, module_id)
    lesson = Lesson(
        module_id=module.id,
        title=title,
        kind="lesson",
        position=await _next_lesson_position(db, module.id),
    )
    db.add(lesson)
    touch_course(course)
    await db.flush()
    return lesson


async def create_quiz_item(
    db: AsyncSession,
    course: Course,
    user: User,
    module_id: str,
    *,
    title: str,
    duration_minutes: int,
    due_at: datetime | None,
) -> Lesson:
    module = await _module_of_course(db, course, module_id)
    lesson = Lesson(
        module_id=module.id,
        title=title,
        kind="quiz",
        position=await _next_lesson_position(db, module.id),
        quiz_config={
            "instructions": "",
            "durationMinutes": duration_minutes,
            "dueAt": due_at.isoformat() if due_at else None,
            "allowRetry": False,
            "allowChatbot": False,
            "questions": [],
            "status": "draft",
        },
    )
    db.add(lesson)
    touch_course(course)
    await db.flush()
    return lesson


async def update_lesson(
    db: AsyncSession, course: Course, user: User, lesson_id: str, title: str
) -> Lesson:
    course_from_lesson, lesson = await course_of_lesson(db, lesson_id)
    if course_from_lesson.id != course.id:
        raise _not_found("Không tìm thấy bài học trong khóa")
    lesson.title = title
    lesson.updated_at = _now()
    touch_course(course)
    await db.flush()
    return lesson


async def delete_lesson(
    db: AsyncSession, course: Course, user: User, lesson_id: str
) -> None:
    _, lesson = await course_of_lesson(db, lesson_id)
    await db.delete(lesson)
    touch_course(course)
    await db.flush()


async def reorder_items(
    db: AsyncSession,
    course: Course,
    user: User,
    module_id: str,
    ordered_lesson_ids: list[str],
) -> None:
    module = await _module_of_course(db, course, module_id)
    lessons = (
        await db.execute(
            select(Lesson).where(Lesson.module_id == module.id).order_by(Lesson.position)
        )
    ).scalars().all()
    by_id = {lesson.id: lesson for lesson in lessons}
    if set(ordered_lesson_ids) != set(by_id):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Danh sách item không khớp cấu trúc chương",
        )
    offset = max((lesson.position for lesson in lessons), default=0) + len(lessons) + 1
    for index, lesson in enumerate(lessons):
        lesson.position = offset + index
    await db.flush()
    for index, lesson_id in enumerate(ordered_lesson_ids):
        by_id[lesson_id].position = index
    touch_course(course)
    await db.flush()
