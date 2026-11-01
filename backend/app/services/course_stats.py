from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import EngagementScore
from app.models.course import Enrollment, Lesson, Module
from app.models.gaze import LearningSession


async def enrollment_counts(db: AsyncSession, course_ids: list[str]) -> dict[str, int]:
    if not course_ids:
        return {}
    stmt = (
        select(Enrollment.course_id, func.count(Enrollment.id))
        .where(Enrollment.course_id.in_(course_ids), Enrollment.status != "dropped")
        .group_by(Enrollment.course_id)
    )
    return {row[0]: row[1] for row in await db.execute(stmt)}


async def attention_avg_by_course(
    db: AsyncSession, course_ids: list[str]
) -> dict[str, float]:
    if not course_ids:
        return {}
    stmt = (
        select(Enrollment.course_id, func.avg(EngagementScore.score))
        .join(EngagementScore, EngagementScore.enrollment_id == Enrollment.id)
        .where(Enrollment.course_id.in_(course_ids))
        .group_by(Enrollment.course_id)
    )
    return {row[0]: float(row[1]) for row in await db.execute(stmt)}


async def session_counts_by_course(
    db: AsyncSession, course_ids: list[str]
) -> dict[str, int]:
    if not course_ids:
        return {}
    stmt = (
        select(Module.course_id, func.count(LearningSession.id))
        .join(Lesson, Lesson.id == LearningSession.lesson_id)
        .join(Module, Module.id == Lesson.module_id)
        .where(Module.course_id.in_(course_ids))
        .group_by(Module.course_id)
    )
    return {row[0]: row[1] for row in await db.execute(stmt)}
