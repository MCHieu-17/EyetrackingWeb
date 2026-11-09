"""Metrics projection từ gaze_samples + presentation/layout.

Một nguồn gaze gốc; mọi dashboard đọc projection `presentation_metrics` hoặc
view SQL. Không giữ bảng aggregate legacy.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload

from app.models.aoi import AoiLayoutSnapshot, PresentationMetric
from app.models.auth import User
from app.models.course import (
    Course,
    CourseVersion,
    CourseVersionItem,
    Enrollment,
    Lesson,
    LessonVersionSlide,
)
from app.models.gaze import (
    ContentPresentation,
    GazeBatch,
    GazeSample,
    LearningSession,
)
from app.models.profile import StudentProfile, UserProfile
from app.schemas.course import StudentLessonOut, StudentRowOut

DEFAULT_ALGORITHM_VERSION = "gaze-metrics-v1"
GRID_SIZE = 24
FIXATION_RADIUS = 0.03
MIN_FIXATION_POINTS = 2
MAX_GAP_MS = 250


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _map_viewport_to_slide(
    x: float, y: float, transform: dict | None
) -> tuple[float, float] | None:
    data = transform or {}
    left = float(data.get("left", 0.0))
    top = float(data.get("top", 0.0))
    width = float(data.get("width", 1.0))
    height = float(data.get("height", 1.0))
    if width <= 0 or height <= 0:
        return None
    return (x - left) / width, (y - top) / height


def _empty_grid() -> list[list[int]]:
    return [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]


def _grid_cell(x: float, y: float) -> tuple[int, int] | None:
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        return None
    return min(GRID_SIZE - 1, int(x * GRID_SIZE)), min(
        GRID_SIZE - 1, int(y * GRID_SIZE)
    )


def _count_fixations(points: list[tuple[float, float]]) -> int:
    fixations = 0
    count = 0
    sum_x = 0.0
    sum_y = 0.0
    for x, y in points:
        if count == 0:
            count = 1
            sum_x, sum_y = x, y
            continue
        cx, cy = sum_x / count, sum_y / count
        if (x - cx) ** 2 + (y - cy) ** 2 <= FIXATION_RADIUS**2:
            count += 1
            sum_x += x
            sum_y += y
        else:
            fixations += int(count >= MIN_FIXATION_POINTS)
            count = 1
            sum_x, sum_y = x, y
    fixations += int(count >= MIN_FIXATION_POINTS)
    return fixations


async def compute_presentation_metrics(
    db: AsyncSession,
    *,
    presentation_id: str,
    algorithm_version: str,
    from_time: datetime,
    to_time: datetime,
    batch_watermark: str | None = None,
) -> PresentationMetric:
    presentation = await db.get(ContentPresentation, presentation_id)
    if presentation is None:
        raise ValueError("presentation not found")

    rows = (
        await db.execute(
            select(
                GazeSample.event_time,
                GazeSample.viewport_x,
                GazeSample.viewport_y,
                GazeSample.status,
                AoiLayoutSnapshot.image_transform,
            )
            .join(GazeBatch, GazeBatch.id == GazeSample.batch_id)
            .outerjoin(
                AoiLayoutSnapshot,
                AoiLayoutSnapshot.id == GazeBatch.layout_snapshot_id,
            )
            .where(
                GazeBatch.presentation_id == presentation_id,
                GazeSample.event_time >= from_time,
                GazeSample.event_time < to_time,
            )
            .order_by(GazeSample.event_time, GazeSample.sequence)
        )
    ).all()

    grid = _empty_grid()
    points: list[tuple[float, float]] = []
    sample_count = 0
    on_slide_count = 0
    dwell_ms = 0
    previous_time: datetime | None = None
    previous_ok = False

    for event_time, viewport_x, viewport_y, status, transform in rows:
        sample_count += 1
        is_ok = (
            status == "ok"
            and viewport_x is not None
            and viewport_y is not None
        )
        if is_ok:
            mapped = _map_viewport_to_slide(
                float(viewport_x), float(viewport_y), transform
            )
            if mapped is not None:
                x, y = mapped
                cell = _grid_cell(x, y)
                if cell is not None:
                    on_slide_count += 1
                    grid[cell[0]][cell[1]] += 1
                    points.append((x, y))
            if previous_ok and previous_time is not None:
                delta = (event_time - previous_time).total_seconds() * 1000
                if 0 <= delta <= MAX_GAP_MS:
                    dwell_ms += int(delta)
        previous_time = event_time
        previous_ok = is_ok

    metric = PresentationMetric(
        presentation_id=presentation_id,
        algorithm_version=algorithm_version,
        batch_watermark=batch_watermark,
        sample_count=sample_count,
        on_slide_count=on_slide_count,
        dwell_ms=dwell_ms,
        fixation_count=_count_fixations(points),
        heatmap_grid=grid,
        computed_at=_now(),
    )
    stmt = pg_insert(PresentationMetric).values(
        presentation_id=metric.presentation_id,
        algorithm_version=metric.algorithm_version,
        batch_watermark=metric.batch_watermark,
        sample_count=metric.sample_count,
        on_slide_count=metric.on_slide_count,
        dwell_ms=metric.dwell_ms,
        fixation_count=metric.fixation_count,
        heatmap_grid=metric.heatmap_grid,
        computed_at=metric.computed_at,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["presentation_id", "algorithm_version"],
        set_={
            "batch_watermark": stmt.excluded.batch_watermark,
            "sample_count": stmt.excluded.sample_count,
            "on_slide_count": stmt.excluded.on_slide_count,
            "dwell_ms": stmt.excluded.dwell_ms,
            "fixation_count": stmt.excluded.fixation_count,
            "heatmap_grid": stmt.excluded.heatmap_grid,
            "computed_at": stmt.excluded.computed_at,
        },
    )
    await db.execute(stmt)
    await db.flush()
    return metric


async def refresh_session_metrics(
    db: AsyncSession,
    *,
    session_id: str,
    from_time: datetime,
    to_time: datetime,
    algorithm_version: str,
    batch_watermark: str | None = None,
) -> list[PresentationMetric]:
    presentations = (
        await db.execute(
            select(ContentPresentation.id).where(
                ContentPresentation.session_id == session_id,
                ContentPresentation.started_at < to_time,
                (ContentPresentation.ended_at.is_(None))
                | (ContentPresentation.ended_at > from_time),
            )
        )
    ).scalars().all()
    out: list[PresentationMetric] = []
    for presentation_id in presentations:
        out.append(
            await compute_presentation_metrics(
                db,
                presentation_id=presentation_id,
                algorithm_version=algorithm_version,
                from_time=from_time,
                to_time=to_time,
                batch_watermark=batch_watermark,
            )
        )
    return out


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
