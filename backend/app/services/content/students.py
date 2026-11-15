"""Course student roster."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.schemas.course import StudentRowOut
from app.services import course_students


async def get_course_students(
    db: AsyncSession, course: Course
) -> list[StudentRowOut]:
    return await course_students.course_students(db, course)
