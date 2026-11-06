"""Helper truy cập dùng chung cho content/media/enrollment (Phase 2)."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import can_access_course, can_manage_course
from app.models.auth import User
from app.models.course import (
    Course,
    CourseVersion,
    CourseVersionItem,
    Lesson,
)


def validate_uuid(value: str, detail: str = "Không tìm thấy bài học") -> None:
    try:
        uuid.UUID(value)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=detail)


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
    return await db.get(Course, lesson.course_id)


async def get_lesson_viewable(db: AsyncSession, lesson_id: str, user: User) -> Lesson:
    lesson = await get_lesson_or_404(db, lesson_id)
    course = await course_of_lesson(db, lesson)
    if course is None or not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    return lesson


def escape_like(q: str) -> str:
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def course_lesson_counts(
    db: AsyncSession, course_ids: list[str]
) -> dict[str, int]:
    """Số item của version published (fallback draft) cho mỗi khóa."""
    counts: dict[str, int] = {}
    if not course_ids:
        return counts
    rows = (
        await db.execute(
            select(Course.id, Course.published_version_id).where(
                Course.id.in_(course_ids)
            )
        )
    ).all()
    for course_id, published_version_id in rows:
        version_id = published_version_id
        if version_id is None:
            version_id = (
                await db.execute(
                    select(CourseVersion.id)
                    .where(
                        CourseVersion.course_id == course_id,
                        CourseVersion.state == "draft",
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
        if version_id is None:
            counts[course_id] = 0
            continue
        counts[course_id] = int(
            (
                await db.execute(
                    select(func.count(CourseVersionItem.id)).where(
                        CourseVersionItem.course_version_id == version_id
                    )
                )
            ).scalar_one()
        )
    return counts
