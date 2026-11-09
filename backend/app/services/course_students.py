"""Course student roster with per-lesson attention/mastery projections."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload

from app.models.aoi import PresentationMetric
from app.models.auth import User
from app.models.course import (
    Course,
    CourseVersion,
    CourseVersionItem,
    Enrollment,
    Lesson,
    LessonVersionSlide,
)
from app.models.gaze import ContentPresentation, LearningSession
from app.models.profile import StudentProfile, UserProfile
from app.schemas.course import StudentLessonOut, StudentRowOut

DEFAULT_ALGORITHM_VERSION = "gaze-metrics-v1"


async def course_students(db: AsyncSession, course: Course) -> list[StudentRowOut]:
    from app.core.helpers import color_for, relative_time_vn

    if course.published_version_id is None:
        return []
    version_id = (
        await db.execute(
            select(CourseVersion.id).where(
                CourseVersion.id == course.published_version_id
            )
        )
    ).scalar_one_or_none()
    if version_id is None:
        return []
    items = (
        await db.execute(
            select(CourseVersionItem, Lesson)
            .join(Lesson, Lesson.id == CourseVersionItem.lesson_id)
            .where(CourseVersionItem.course_version_id == version_id)
            .order_by(CourseVersionItem.position)
            .options(raiseload(Lesson.versions), raiseload(Lesson.slides))
        )
    ).all()

    rows = (
        await db.execute(
            select(Enrollment, User, UserProfile, StudentProfile)
            .join(User, User.id == Enrollment.student_id)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
            .where(Enrollment.course_id == course.id)
            .order_by(Enrollment.enrolled_at)
            .options(
                raiseload(Enrollment.course),
                raiseload(User.profile),
                raiseload(User.roles),
            )
        )
    ).all()
    if not rows:
        return []

    enrollment_ids = [enrollment.id for enrollment, _, _, _ in rows]
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

    lesson_version_ids = list(
        dict.fromkeys(item.lesson_version_id for item, _ in items)
    )
    slides_by_version: dict[str, list[str]] = {}
    if lesson_version_ids:
        slide_rows = (
            await db.execute(
                select(
                    LessonVersionSlide.lesson_version_id,
                    LessonVersionSlide.id,
                )
                .where(
                    LessonVersionSlide.lesson_version_id.in_(
                        lesson_version_ids
                    )
                )
                .order_by(
                    LessonVersionSlide.lesson_version_id,
                    LessonVersionSlide.position,
                )
            )
        ).all()
        for lesson_version_id, slide_id in slide_rows:
            slides_by_version.setdefault(lesson_version_id, []).append(slide_id)

    slide_ids = [
        slide_id for ids in slides_by_version.values() for slide_id in ids
    ]
    metrics_by_enrollment_slide: dict[tuple[str, str], tuple[int, int, int]] = {}
    if slide_ids:
        metric_rows = (
            await db.execute(
                select(
                    ContentPresentation.lesson_version_slide_id,
                    LearningSession.enrollment_id,
                    func.coalesce(func.sum(PresentationMetric.sample_count), 0),
                    func.coalesce(
                        func.sum(PresentationMetric.on_slide_count), 0
                    ),
                    func.coalesce(func.sum(PresentationMetric.dwell_ms), 0),
                )
                .join(
                    ContentPresentation,
                    ContentPresentation.id == PresentationMetric.presentation_id,
                )
                .join(
                    LearningSession,
                    LearningSession.id == ContentPresentation.session_id,
                )
                .where(
                    LearningSession.enrollment_id.in_(enrollment_ids),
                    ContentPresentation.lesson_version_slide_id.in_(slide_ids),
                    PresentationMetric.algorithm_version
                    == DEFAULT_ALGORITHM_VERSION,
                )
                .group_by(
                    ContentPresentation.lesson_version_slide_id,
                    LearningSession.enrollment_id,
                )
            )
        ).all()
        metrics_by_enrollment_slide = {
            (enrollment_id, slide_id): (
                int(sample_count),
                int(on_slide_count),
                int(dwell_ms),
            )
            for slide_id, enrollment_id, sample_count, on_slide_count, dwell_ms
            in metric_rows
        }

    out: list[StudentRowOut] = []
    for enrollment, student, profile, student_profile in rows:
        lessons: list[StudentLessonOut] = []
        for item, lesson in items:
            if lesson.kind == "quiz":
                lessons.append(
                    StudentLessonOut(
                        lesson_id=lesson.id,
                        attention=None,
                        mastery=None,
                    )
                )
                continue

            slides = slides_by_version.get(item.lesson_version_id, [])
            total_samples = 0
            on_slide_samples = 0
            viewed_total = 0
            for slide_id in slides:
                sample_count, on_slide_count, dwell_ms = (
                    metrics_by_enrollment_slide.get(
                        (enrollment.id, slide_id), (0, 0, 0)
                    )
                )
                total_samples += sample_count
                on_slide_samples += on_slide_count
                if dwell_ms > 0:
                    viewed_total += 1

            attention = (
                round(on_slide_samples / total_samples * 100, 1)
                if total_samples
                else None
            )
            mastery = (
                round(100 * viewed_total / len(slides), 1) if slides else None
            )
            lessons.append(
                StudentLessonOut(
                    lesson_id=lesson.id,
                    attention=attention,
                    mastery=mastery,
                )
            )
        attentions = [
            item.attention for item in lessons if item.attention is not None
        ]
        out.append(
            StudentRowOut(
                id=student.id,
                name=profile.full_name if profile else student.email,
                code=student_profile.student_code if student_profile else "",
                color=color_for(student.id),
                avatar_url=profile.avatar_url if profile else None,
                attention=(
                    round(sum(attentions) / len(attentions), 1)
                    if attentions
                    else None
                ),
                last_active=relative_time_vn(last_active.get(enrollment.id)),
                status=enrollment.status,
                lessons=lessons,
            )
        )
    return out
