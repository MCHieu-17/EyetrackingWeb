"""Aggregate stats cho danh sách khóa học của giáo viên.

Ba aggregate (enrollment, session, attention) chạy trong một statement và
được cache ngắn hạn theo từng course để lần mở trang sau không quét lại
`content_views`.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rediscache import delete as cache_delete
from app.core.rediscache import get_many_json, set_json
from app.models.course import Course, CourseModule, Enrollment, Lesson
from app.models.gaze import ContentView, LearningSession
from app.services import metrics

_STATS_TTL_SECONDS = 45
_ANALYSIS_VERSIONS = (
    "gaze-metrics-v2",
    "gaze-metrics-v3",
    "gaze-metrics-v4",
    "gaze-metrics-v5",
    "gaze-metrics-v6",
    "gaze-metrics-v7",
    metrics.ANALYSIS_VERSION,
)


def _stats_key(course_id: str) -> str:
    return f"course:stats:{course_id}"


async def course_rollup(
    db: AsyncSession, course_ids: list[str]
) -> dict[str, dict]:
    """Trả students/sessions/attention của nhiều course trong một query."""
    if not course_ids:
        return {}

    enrollments = (
        select(
            Enrollment.course_id,
            func.count(Enrollment.id).label("students"),
        )
        .where(Enrollment.course_id.in_(course_ids), Enrollment.status != "dropped")
        .group_by(Enrollment.course_id)
        .subquery()
    )
    sessions = (
        select(
            CourseModule.course_id,
            func.count(LearningSession.id).label("sessions"),
        )
        .join(Lesson, Lesson.module_id == CourseModule.id)
        .join(LearningSession, LearningSession.lesson_id == Lesson.id)
        .where(CourseModule.course_id.in_(course_ids))
        .group_by(CourseModule.course_id)
        .subquery()
    )
    attention = (
        select(
            CourseModule.course_id,
            func.sum(ContentView.on_slide_gaze_count).label("on_slide"),
            func.sum(ContentView.gaze_count).label("gaze"),
        )
        .join(Lesson, Lesson.module_id == CourseModule.id)
        .join(LearningSession, LearningSession.lesson_id == Lesson.id)
        .join(ContentView, ContentView.session_id == LearningSession.id)
        .where(
            CourseModule.course_id.in_(course_ids),
            ContentView.analysis_version.in_(_ANALYSIS_VERSIONS),
            ContentView.surface == "lesson",
        )
        .group_by(CourseModule.course_id)
        .subquery()
    )
    stmt = (
        select(
            Course.id,
            func.coalesce(enrollments.c.students, 0),
            func.coalesce(sessions.c.sessions, 0),
            attention.c.on_slide,
            attention.c.gaze,
        )
        .outerjoin(enrollments, enrollments.c.course_id == Course.id)
        .outerjoin(sessions, sessions.c.course_id == Course.id)
        .outerjoin(attention, attention.c.course_id == Course.id)
        .where(Course.id.in_(course_ids))
    )

    out: dict[str, dict] = {}
    for course_id, students, session_count, on_slide, gaze in await db.execute(stmt):
        out[course_id] = {
            "students": int(students or 0),
            "sessions": int(session_count or 0),
            "attention": (
                round(float(on_slide) / float(gaze) * 100, 1) if gaze else None
            ),
        }
    return out


async def course_rollup_cached(
    db: AsyncSession, course_ids: list[str]
) -> dict[str, dict]:
    """Đọc cache theo course; chỉ query các course còn thiếu."""
    if not course_ids:
        return {}

    keys = [_stats_key(course_id) for course_id in course_ids]
    cached = await get_many_json(keys)
    out = {
        course_id: value
        for course_id, value in zip(course_ids, cached)
        if isinstance(value, dict)
    }
    missing = [course_id for course_id in course_ids if course_id not in out]
    if not missing:
        return out

    fresh = await course_rollup(db, missing)
    writes = []
    for course_id in missing:
        value = fresh.get(
            course_id, {"students": 0, "sessions": 0, "attention": None}
        )
        out[course_id] = value
        writes.append(set_json(_stats_key(course_id), value, _STATS_TTL_SECONDS))
    if writes:
        await asyncio.gather(*writes)
    return out


async def invalidate_course_stats(course_id: str) -> None:
    await cache_delete(_stats_key(course_id))
