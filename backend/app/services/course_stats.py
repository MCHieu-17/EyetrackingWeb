from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aoi import PresentationMetric
from app.models.course import (
    CourseVersion,
    CourseVersionItem,
    Enrollment,
)
from app.models.gaze import ContentPresentation, LearningSession


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
        select(
            CourseVersion.course_id,
            func.sum(PresentationMetric.on_slide_count),
            func.sum(PresentationMetric.sample_count),
        )
        .join(
            CourseVersionItem,
            CourseVersionItem.course_version_id == CourseVersion.id,
        )
        .join(
            LearningSession,
            LearningSession.course_version_item_id == CourseVersionItem.id,
        )
        .join(
            ContentPresentation,
            ContentPresentation.session_id == LearningSession.id,
        )
        .join(
            PresentationMetric,
            PresentationMetric.presentation_id == ContentPresentation.id,
        )
        .where(
            CourseVersion.course_id.in_(course_ids),
            PresentationMetric.algorithm_version == "gaze-metrics-v1",
        )
        .group_by(CourseVersion.course_id)
    )
    out: dict[str, float] = {}
    for course_id, on_slide, total in await db.execute(stmt):
        if total:
            out[course_id] = round(float(on_slide) / float(total) * 100, 1)
    return out


async def session_counts_by_course(
    db: AsyncSession, course_ids: list[str]
) -> dict[str, int]:
    if not course_ids:
        return {}
    stmt = (
        select(CourseVersion.course_id, func.count(LearningSession.id))
        .join(
            CourseVersionItem,
            CourseVersionItem.course_version_id == CourseVersion.id,
        )
        .join(
            LearningSession,
            LearningSession.course_version_item_id == CourseVersionItem.id,
        )
        .where(CourseVersion.course_id.in_(course_ids))
        .group_by(CourseVersion.course_id)
    )
    return {row[0]: row[1] for row in await db.execute(stmt)}
