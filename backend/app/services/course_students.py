"""Course student roster with per-lesson attention/mastery projections."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.course import Course, CourseModule, Enrollment, Lesson, Slide
from app.models.gaze import ContentView, LearningSession
from app.models.profile import StudentProfile
from app.schemas.course import StudentLessonOut, StudentRowOut

DEFAULT_ALGORITHM_VERSION = "gaze-metrics-v3"


async def course_students(db: AsyncSession, course: Course) -> list[StudentRowOut]:
    from app.core.helpers import color_for, relative_time_vn

    modules = (
        await db.execute(
            select(CourseModule.id)
            .where(CourseModule.course_id == course.id)
            .order_by(CourseModule.position)
        )
    ).scalars().all()
    if not modules:
        return []
    lessons = (
        await db.execute(
            select(Lesson)
            .where(Lesson.module_id.in_(modules))
            .order_by(Lesson.position)
        )
    ).scalars().all()

    rows = (
        await db.execute(
            select(Enrollment, User, StudentProfile)
            .join(User, User.id == Enrollment.student_id)
            .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
            .where(Enrollment.course_id == course.id)
            .order_by(Enrollment.enrolled_at)
        )
    ).all()
    if not rows:
        return []

    enrollment_ids = [enrollment.id for enrollment, _, _ in rows]
    last_active = dict(
        (
            await db.execute(
                select(
                    LearningSession.enrollment_id,
                    func.max(LearningSession.started_at),
                )
                .where(LearningSession.enrollment_id.in_(enrollment_ids))
                .group_by(LearningSession.enrollment_id)
            )
        ).all()
    )

    slides_by_lesson: dict[str, list[str]] = {}
    slide_rows = (
        await db.execute(
            select(Slide.lesson_id, Slide.id)
            .where(Slide.lesson_id.in_([lesson.id for lesson in lessons]))
            .order_by(Slide.lesson_id, Slide.position)
        )
    ).all()
    for lesson_id, slide_id in slide_rows:
        slides_by_lesson.setdefault(lesson_id, []).append(slide_id)

    metrics_by_enrollment_slide: dict[tuple[str, str], tuple[int, int, int]] = {}
    metric_rows = (
        await db.execute(
            select(
                ContentView.slide_id,
                LearningSession.enrollment_id,
                func.coalesce(func.sum(ContentView.gaze_count), 0),
                func.coalesce(func.sum(ContentView.on_slide_gaze_count), 0),
                func.coalesce(func.sum(ContentView.tracked_duration_ms), 0),
            )
            .join(LearningSession, LearningSession.id == ContentView.session_id)
            .where(
                LearningSession.enrollment_id.in_(enrollment_ids),
                ContentView.analysis_version.in_(
                    ("gaze-metrics-v2", DEFAULT_ALGORITHM_VERSION)
                ),
                ContentView.slide_id.is_not(None),
            )
            .group_by(ContentView.slide_id, LearningSession.enrollment_id)
        )
    ).all()
    for slide_id, enrollment_id, gaze_count, on_slide_count, dwell_ms in metric_rows:
        metrics_by_enrollment_slide[(enrollment_id, slide_id)] = (
            int(gaze_count),
            int(on_slide_count),
            int(dwell_ms),
        )

    out: list[StudentRowOut] = []
    for enrollment, student, student_profile in rows:
        lesson_stats: list[StudentLessonOut] = []
        for lesson in lessons:
            if lesson.kind == "quiz":
                lesson_stats.append(
                    StudentLessonOut(
                        lesson_id=lesson.id,
                        attention=None,
                        mastery=None,
                    )
                )
                continue

            slides = slides_by_lesson.get(lesson.id, [])
            total_gaze = on_slide_gaze = viewed_total = 0
            for slide_id in slides:
                gaze_count, on_slide_count, dwell_ms = (
                    metrics_by_enrollment_slide.get(
                        (enrollment.id, slide_id), (0, 0, 0)
                    )
                )
                total_gaze += gaze_count
                on_slide_gaze += on_slide_count
                if dwell_ms > 0:
                    viewed_total += 1

            attention = (
                round(on_slide_gaze / total_gaze * 100, 1) if total_gaze else None
            )
            mastery = (
                round(100 * viewed_total / len(slides), 1) if slides else None
            )
            lesson_stats.append(
                StudentLessonOut(
                    lesson_id=lesson.id,
                    attention=attention,
                    mastery=mastery,
                )
            )
        attentions = [
            item.attention for item in lesson_stats if item.attention is not None
        ]
        out.append(
            StudentRowOut(
                id=student.id,
                name=student.full_name or student.email,
                code=student_profile.student_code if student_profile else "",
                color=color_for(student.id),
                avatar_url=student.avatar_url,
                attention=(
                    round(sum(attentions) / len(attentions), 1)
                    if attentions
                    else None
                ),
                last_active=relative_time_vn(last_active.get(enrollment.id)),
                status=enrollment.status,
                lessons=lesson_stats,
            )
        )
    return out
