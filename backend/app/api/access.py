"""Access helpers dùng chung."""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import can_access_course, can_manage_course
from app.core.helpers import escape_like as escape_like  # re-export
from app.models.auth import User
from app.models.course import Course, CourseModule, Lesson
from app.services.access import validate_uuid as validate_uuid  # re-export


async def get_course_or_404(db: AsyncSession, course_id: str) -> Course:
    course = await db.get(Course, course_id)
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
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài học")
    return lesson


async def course_of_lesson(db: AsyncSession, lesson: Lesson) -> Course | None:
    module = await db.get(CourseModule, lesson.module_id)
    if module is None:
        return None
    return await db.get(Course, module.course_id)


async def get_lesson_with_course(
    db: AsyncSession, lesson_id: str
) -> tuple[Lesson, Course]:
    lesson = await get_lesson_or_404(db, lesson_id)
    course = await course_of_lesson(db, lesson)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    return lesson, course


async def get_managed_lesson(
    db: AsyncSession, lesson_id: str, user: User
) -> tuple[Lesson, Course]:
    lesson, course = await get_lesson_with_course(db, lesson_id)
    if not await can_manage_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    return lesson, course


async def get_viewable_lesson(
    db: AsyncSession, lesson_id: str, user: User
) -> tuple[Lesson, Course]:
    lesson = await get_lesson_or_404(db, lesson_id)
    course = await course_of_lesson(db, lesson)
    if course is None or not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    return lesson, course


async def get_lesson_viewable(db: AsyncSession, lesson_id: str, user: User) -> Lesson:
    lesson, _ = await get_viewable_lesson(db, lesson_id, user)
    return lesson
