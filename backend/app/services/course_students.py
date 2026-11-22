"""Course student roster with per-lesson attention/mastery projections."""

from __future__ import annotations

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.course import Course, CourseModule, Enrollment, Lesson, Slide
from app.models.gaze import ContentView, LearningSession
from app.models.profile import StudentProfile
from app.schemas.course import StudentLessonOut, StudentRowOut
from app.services import metrics

DEFAULT_ALGORITHM_VERSION = metrics.ANALYSIS_VERSION
_ANALYSIS_VERSIONS = (
    "gaze-metrics-v2",
    "gaze-metrics-v3",
    "gaze-metrics-v4",
    "gaze-metrics-v5",
    "gaze-metrics-v6",
    "gaze-metrics-v7",
    DEFAULT_ALGORITHM_VERSION,
)


async def _course_lessons(
    db: AsyncSession, course_id: str
) -> list[Lesson]:
    return list(
        (
            await db.execute(
                select(Lesson)
                .join(CourseModule, CourseModule.id == Lesson.module_id)
                .where(CourseModule.course_id == course_id)
                .order_by(CourseModule.position, Lesson.position)
            )
        ).scalars()
    )


async def _lesson_metrics(
    db: AsyncSession, enrollment_ids: list[str], *, with_viewed: bool = True
) -> dict[tuple[str, str], tuple[int, int, int]]:
    """(enrollment, lesson) -> (gaze, on_slide, số slide có dwell > 0).

    `with_viewed=False` bỏ `count(distinct)` (chỉ cần cho mastery), tránh sort
    theo slide ở màn danh sách học viên.
    """
    columns = [
        LearningSession.enrollment_id,
        LearningSession.lesson_id,
        func.coalesce(func.sum(ContentView.gaze_count), 0),
        func.coalesce(func.sum(ContentView.on_slide_gaze_count), 0),
    ]
    if with_viewed:
        viewed_slides = func.count(distinct(ContentView.slide_id)).filter(
            ContentView.tracked_duration_ms > 0
        )
        columns.append(func.coalesce(viewed_slides, 0))
    rows = (
        await db.execute(
            select(*columns)
            .join(ContentView, ContentView.session_id == LearningSession.id)
            .where(
                LearningSession.enrollment_id.in_(enrollment_ids),
                ContentView.analysis_version.in_(_ANALYSIS_VERSIONS),
                ContentView.slide_id.is_not(None),
            )
            .group_by(
                LearningSession.enrollment_id, LearningSession.lesson_id
            )
        )
    ).all()
    out: dict[tuple[str, str], tuple[int, int, int]] = {}
    for row in rows:
        out[(row[0], row[1])] = (
            int(row[2]),
            int(row[3]),
            int(row[4]) if with_viewed else 0,
        )
    return out


async def _slides_by_lesson(
    db: AsyncSession, lesson_ids: list[str]
) -> dict[str, list[str]]:
    slides_by_lesson: dict[str, list[str]] = {}
    if not lesson_ids:
        return slides_by_lesson
    rows = (
        await db.execute(
            select(Slide.lesson_id, Slide.id)
            .where(Slide.lesson_id.in_(lesson_ids))
            .order_by(Slide.lesson_id, Slide.position)
        )
    ).all()
    for lesson_id, slide_id in rows:
        slides_by_lesson.setdefault(lesson_id, []).append(slide_id)
    return slides_by_lesson


def _lesson_stats(
    lessons: list[Lesson],
    metrics_by_lesson: dict[tuple[str, str], tuple[int, int, int]],
    slides_by_lesson: dict[str, list[str]],
    enrollment_id: str,
) -> tuple[list[StudentLessonOut], list[float]]:
    out: list[StudentLessonOut] = []
    attentions: list[float] = []
    for lesson in lessons:
        if lesson.kind == "quiz":
            continue

        gaze_count, on_slide_count, viewed_count = metrics_by_lesson.get(
            (enrollment_id, lesson.id), (0, 0, 0)
        )
        attention = (
            round(on_slide_count / gaze_count * 100, 1)
            if gaze_count
            else None
        )
        if attention is not None:
            attentions.append(attention)

        slides = slides_by_lesson.get(lesson.id, [])
        mastery = round(100 * viewed_count / len(slides), 1) if slides else None
        out.append(
            StudentLessonOut(
                lesson_id=lesson.id,
                attention=attention,
                mastery=mastery,
            )
        )
    return out, attentions


async def course_students(
    db: AsyncSession,
    course: Course,
    *,
    include_lessons: bool = True,
    student_id: str | None = None,
) -> list[StudentRowOut]:
    from app.core.helpers import color_for, relative_time_vn

    lessons = await _course_lessons(db, course.id)
    if not lessons:
        return []

    filters = [
        Enrollment.course_id == course.id,
        # "Xóa" chỉ đánh dấu dropped để giữ nguyên dữ liệu học tập;
        # danh sách Học viên không hiển thị các enrollment này.
        Enrollment.status != "dropped",
    ]
    if student_id is not None:
        filters.append(Enrollment.student_id == student_id)

    rows = (
        await db.execute(
            select(Enrollment, User, StudentProfile)
            .join(User, User.id == Enrollment.student_id)
            .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
            .where(*filters)
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
    metrics_by_lesson = await _lesson_metrics(
        db, enrollment_ids, with_viewed=include_lessons
    )
    slides_by_lesson = (
        await _slides_by_lesson(db, [lesson.id for lesson in lessons])
        if include_lessons
        else {}
    )

    out: list[StudentRowOut] = []
    for enrollment, student, student_profile in rows:
        lesson_stats: list[StudentLessonOut] = []
        attentions: list[float] = []
        if include_lessons:
            lesson_stats, attentions = _lesson_stats(
                lessons, metrics_by_lesson, slides_by_lesson, enrollment.id
            )
        else:
            # Chỉ cần attention tổng; không dựng Pydantic cho từng bài.
            for lesson in lessons:
                if lesson.kind == "quiz":
                    continue
                gaze_count, on_slide_count, _ = metrics_by_lesson.get(
                    (enrollment.id, lesson.id), (0, 0, 0)
                )
                if gaze_count:
                    attentions.append(
                        round(on_slide_count / gaze_count * 100, 1)
                    )

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


async def course_student_lessons(
    db: AsyncSession, course: Course, student_id: str
) -> list[StudentLessonOut] | None:
    enrollment_id = (
        await db.execute(
            select(Enrollment.id).where(
                Enrollment.course_id == course.id,
                Enrollment.student_id == student_id,
                Enrollment.status != "dropped",
            )
        )
    ).scalar_one_or_none()
    if enrollment_id is None:
        return None

    lessons = await _course_lessons(db, course.id)
    if not lessons:
        return []
    metrics_by_lesson = await _lesson_metrics(db, [enrollment_id])
    slides_by_lesson = await _slides_by_lesson(
        db, [lesson.id for lesson in lessons]
    )
    lesson_stats, _ = _lesson_stats(
        lessons, metrics_by_lesson, slides_by_lesson, enrollment_id
    )
    return lesson_stats
