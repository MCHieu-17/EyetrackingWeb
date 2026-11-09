"""Course student roster."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.schemas.course import StudentRowOut


async def get_course_students(
    db: AsyncSession, course: Course
) -> list[StudentRowOut]:
    from app.services import metrics

    return await metrics.course_students(db, course)
