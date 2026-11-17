from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import CourseModule, Enrollment, Lesson
from app.models.gaze import ContentView, LearningSession


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
            CourseModule.course_id,
            func.sum(ContentView.on_slide_gaze_count),
            func.sum(ContentView.gaze_count),
        )
        .join(Lesson, Lesson.module_id == CourseModule.id)
        .join(LearningSession, LearningSession.lesson_id == Lesson.id)
        .join(ContentView, ContentView.session_id == LearningSession.id)
        .where(
            CourseModule.course_id.in_(course_ids),
            ContentView.analysis_version.in_(
                (
                    "gaze-metrics-v2",
                    "gaze-metrics-v3",
                    "gaze-metrics-v4",
                    "gaze-metrics-v5",
                    "gaze-metrics-v6",
                    "gaze-metrics-v7",
                )
            ),
            ContentView.surface == "lesson",
        )
        .group_by(CourseModule.course_id)
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
        select(CourseModule.course_id, func.count(LearningSession.id))
        .join(Lesson, Lesson.module_id == CourseModule.id)
        .join(LearningSession, LearningSession.lesson_id == Lesson.id)
        .where(CourseModule.course_id.in_(course_ids))
        .group_by(CourseModule.course_id)
    )
    return {row[0]: row[1] for row in await db.execute(stmt)}
