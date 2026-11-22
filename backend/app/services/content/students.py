"""Course student roster."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rediscache import get_json, set_json
from app.models.course import Course
from app.schemas.course import StudentLessonOut, StudentRowOut
from app.services import course_students

_STUDENTS_TTL_SECONDS = 10


async def get_course_students(
    db: AsyncSession, course: Course
) -> list[StudentRowOut]:
    cache_key = f"course:students:{course.id}"
    cached = await get_json(cache_key)
    if isinstance(cached, list):
        return [StudentRowOut.model_validate(item) for item in cached]

    rows = await course_students.course_students(
        db, course, include_lessons=False
    )
    await set_json(
        cache_key,
        [item.model_dump(mode="json") for item in rows],
        _STUDENTS_TTL_SECONDS,
    )
    return rows


async def get_course_student_lessons(
    db: AsyncSession, course: Course, student_id: str
) -> list[StudentLessonOut] | None:
    return await course_students.course_student_lessons(db, course, student_id)
