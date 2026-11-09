"""Helper truy cập dùng chung cho content/media/enrollment (Phase 2)."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload

from app.api.deps import can_access_course, can_manage_course
from app.core.helpers import escape_like as escape_like  # re-export cho API cũ
from app.models.auth import User
from app.models.course import Course, Lesson


def validate_uuid(value: str, detail: str = "Không tìm thấy bài học") -> None:
    try:
        uuid.UUID(value)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=detail)


async def get_course_or_404(db: AsyncSession, course_id: str) -> Course:
    course = await db.get(
        Course,
        course_id,
        options=[
            raiseload(Course.versions),
            raiseload(Course.enrollments),
            raiseload(Course.owner),
            raiseload(Course.creator),
        ],
    )
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    return course


async def get_owned_course(db: AsyncSession, course_id: str, user: User) -> Course:
    course = await get_course_or_404(db, course_id)
    if not await can_manage_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    return course


async def get_viewable_course(db: AsyncSession, course_id: str, user: User) -> Course:
    course = await get_course_or_404(db, course_id)
    if not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    return course


async def get_lesson_or_404(db: AsyncSession, lesson_id: str) -> Lesson:
    validate_uuid(lesson_id)
    lesson = await db.get(
        Lesson,
        lesson_id,
        options=[
            raiseload(Lesson.versions),
            raiseload(Lesson.slides),
        ],
    )
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài học")
    return lesson


async def course_of_lesson(db: AsyncSession, lesson: Lesson) -> Course | None:
    return await db.get(
        Course,
        lesson.course_id,
        options=[
            raiseload(Course.versions),
            raiseload(Course.enrollments),
            raiseload(Course.owner),
            raiseload(Course.creator),
        ],
    )


async def get_lesson_viewable(db: AsyncSession, lesson_id: str, user: User) -> Lesson:
    lesson = await get_lesson_or_404(db, lesson_id)
    course = await course_of_lesson(db, lesson)
    if course is None or not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    return lesson
