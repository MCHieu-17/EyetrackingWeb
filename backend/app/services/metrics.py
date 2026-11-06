"""Metrics projection từ gaze_samples + presentation/layout.

Một nguồn gaze gốc; mọi dashboard đọc projection `presentation_metrics` hoặc
view SQL. Không giữ bảng aggregate legacy.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.schemas.analytics import HotspotOut, SlideStatOut
from app.schemas.course import StudentLessonOut, StudentRowOut

DEFAULT_ALGORITHM_VERSION = "gaze-metrics-v1"
GRID_SIZE = 24
FIXATION_RADIUS = 0.03
MIN_FIXATION_POINTS = 2
MAX_GAP_MS = 250
MAX_POINTS = 300
HOTSPOT_TOP_N = 5


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


def _hotspots(grid: list[list[int]]) -> list[HotspotOut]:
    total = sum(sum(row) for row in grid)
    if total <= 0:
        return []
    candidates: list[tuple[float, float, int]] = []
    for i in range(GRID_SIZE):
        for j in range(GRID_SIZE):
            weight = grid[i][j]
            if weight < max(2, total * 0.01):
                continue
            neighbours = [
                grid[a][b]
                for a in range(max(0, i - 1), min(GRID_SIZE, i + 2))
                for b in range(max(0, j - 1), min(GRID_SIZE, j + 2))
            ]
            if weight >= max(neighbours):
                candidates.append(
                    ((i + 0.5) / GRID_SIZE, (j + 0.5) / GRID_SIZE, weight)
                )
    candidates.sort(key=lambda item: -item[2])
    out: list[HotspotOut] = []
    for x, y, weight in candidates:
        if any((x - item.x) ** 2 + (y - item.y) ** 2 < 0.12**2 for item in out):
            continue
        out.append(
            HotspotOut(
                x=round(x, 4),
                y=round(y, 4),
                r=0.08,
                w=round(weight / total, 4),
            )
        )
        if len(out) >= HOTSPOT_TOP_N:
            break
    return out


def _merge_grids(grids: list[list[list[int]]]) -> list[list[int]]:
    merged = _empty_grid()
    for grid in grids:
        if not isinstance(grid, list):
            continue
        for i, row in enumerate(grid[:GRID_SIZE]):
            if not isinstance(row, list):
                continue
            for j, value in enumerate(row[:GRID_SIZE]):
                try:
                    merged[i][j] += int(value)
                except (TypeError, ValueError):
                    continue
    return merged


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


async def _published_item_for_lesson(
    db: AsyncSession, lesson_id: str
) -> tuple[Course, CourseVersion, CourseVersionItem] | None:
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        return None
    course = await db.get(Course, lesson.course_id)
    if course is None or course.published_version_id is None:
        return None
    version = await db.get(CourseVersion, course.published_version_id)
    if version is None:
        return None
    item = (
        await db.execute(
            select(CourseVersionItem).where(
                CourseVersionItem.course_version_id == version.id,
                CourseVersionItem.lesson_id == lesson.id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        return None
    return course, version, item


async def lesson_heatmap(
    db: AsyncSession,
    lesson_id: str,
    student_id: str | None = None,
    algorithm_version: str = DEFAULT_ALGORITHM_VERSION,
) -> list[SlideStatOut]:
    resolved = await _published_item_for_lesson(db, lesson_id)
    if resolved is None:
        return []
    _, _, item = resolved
    slides = (
        await db.execute(
            select(LessonVersionSlide)
            .where(LessonVersionSlide.lesson_version_id == item.lesson_version_id)
            .order_by(LessonVersionSlide.position)
        )
    ).scalars().all()
    if not slides:
        return []

    out: list[SlideStatOut] = []
    for index, slide in enumerate(slides):
        stmt = (
            select(
                func.coalesce(func.sum(PresentationMetric.sample_count), 0),
                func.coalesce(func.sum(PresentationMetric.on_slide_count), 0),
                func.coalesce(func.sum(PresentationMetric.dwell_ms), 0),
                func.coalesce(func.sum(PresentationMetric.fixation_count), 0),
                func.count(func.distinct(ContentPresentation.session_id)),
            )
            .join(
                ContentPresentation,
                ContentPresentation.id == PresentationMetric.presentation_id,
            )
            .where(
                ContentPresentation.lesson_version_slide_id == slide.id,
                PresentationMetric.algorithm_version == algorithm_version,
            )
        )
        if student_id:
            stmt = stmt.join(
                LearningSession,
                LearningSession.id == ContentPresentation.session_id,
            ).join(
                Enrollment, Enrollment.id == LearningSession.enrollment_id
            ).where(Enrollment.student_id == student_id)
        sample_count, on_slide_count, dwell_ms, fixations, sessions = (
            await db.execute(stmt)
        ).one()

        grid_stmt = (
            select(PresentationMetric.heatmap_grid)
            .join(
                ContentPresentation,
                ContentPresentation.id == PresentationMetric.presentation_id,
            )
            .where(
                ContentPresentation.lesson_version_slide_id == slide.id,
                PresentationMetric.algorithm_version == algorithm_version,
            )
        )
        if student_id:
            grid_stmt = (
                grid_stmt.join(
                    LearningSession,
                    LearningSession.id == ContentPresentation.session_id,
                )
                .join(
                    Enrollment, Enrollment.id == LearningSession.enrollment_id
                )
                .where(Enrollment.student_id == student_id)
            )
        grids = (await db.execute(grid_stmt)).scalars().all()
        grid = _merge_grids(list(grids))

        points: list[list[float]] = []
        point_stmt = (
            select(
                GazeSample.viewport_x,
                GazeSample.viewport_y,
                AoiLayoutSnapshot.image_transform,
            )
            .join(GazeBatch, GazeBatch.id == GazeSample.batch_id)
            .join(
                ContentPresentation,
                ContentPresentation.id == GazeBatch.presentation_id,
            )
            .outerjoin(
                AoiLayoutSnapshot,
                AoiLayoutSnapshot.id == GazeBatch.layout_snapshot_id,
            )
            .where(
                ContentPresentation.lesson_version_slide_id == slide.id,
                GazeSample.status == "ok",
            )
        )
        if student_id:
            point_stmt = (
                point_stmt.join(
                    LearningSession,
                    LearningSession.id == ContentPresentation.session_id,
                )
                .join(
                    Enrollment, Enrollment.id == LearningSession.enrollment_id
                )
                .where(Enrollment.student_id == student_id)
            )
        point_rows = (
            await db.execute(
                point_stmt.order_by(GazeSample.event_time).limit(5000)
            )
        ).all()
        for viewport_x, viewport_y, transform in point_rows:
            if viewport_x is None or viewport_y is None:
                continue
            mapped = _map_viewport_to_slide(
                float(viewport_x), float(viewport_y), transform
            )
            if mapped is None:
                continue
            x, y = mapped
            if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
                points.append([round(x, 4), round(y, 4)])
        if len(points) > MAX_POINTS:
            step = len(points) / MAX_POINTS
            points = [points[int(i * step)] for i in range(MAX_POINTS)]

        out.append(
            SlideStatOut(
                idx=index,
                on_slide=round(on_slide_count / sample_count * 100, 1)
                if sample_count
                else 0.0,
                fixations=int(fixations),
                view_sec=round(dwell_ms / 1000 / max(1, int(sessions)), 1),
                hotspots=_hotspots(grid),
                points=points,
            )
        )
    return out


async def course_students(db: AsyncSession, course: Course) -> list[StudentRowOut]:
    from app.core.helpers import color_for, relative_time_vn

    if course.published_version_id is None:
        return []
    version = await db.get(CourseVersion, course.published_version_id)
    if version is None:
        return []
    items = (
        await db.execute(
            select(CourseVersionItem)
            .where(CourseVersionItem.course_version_id == version.id)
            .order_by(CourseVersionItem.position)
        )
    ).scalars().all()

    rows = (
        await db.execute(
            select(Enrollment, User, UserProfile, StudentProfile)
            .join(User, User.id == Enrollment.student_id)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
            .where(Enrollment.course_id == course.id)
            .order_by(Enrollment.enrolled_at)
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

    out: list[StudentRowOut] = []
    for enrollment, student, profile, student_profile in rows:
        lessons: list[StudentLessonOut] = []
        for item in items:
            lesson = await db.get(Lesson, item.lesson_id)
            if lesson is None:
                continue
            if lesson.kind == "quiz":
                lessons.append(
                    StudentLessonOut(
                        lesson_id=lesson.id,
                        attention=None,
                        mastery=None,
                        key_done=0,
                        key_total=0,
                    )
                )
                continue

            slides = (
                await db.execute(
                    select(LessonVersionSlide)
                    .where(
                        LessonVersionSlide.lesson_version_id
                        == item.lesson_version_id
                    )
                    .order_by(LessonVersionSlide.position)
                )
            ).scalars().all()
            total_samples = 0
            on_slide_samples = 0
            key_total = sum(1 for slide in slides if slide.is_key)
            key_done = 0
            normal_total = sum(1 for slide in slides if not slide.is_key)
            normal_done = 0
            for slide in slides:
                sample_count, on_slide_count, dwell_ms = (
                    await db.execute(
                        select(
                            func.coalesce(
                                func.sum(PresentationMetric.sample_count), 0
                            ),
                            func.coalesce(
                                func.sum(PresentationMetric.on_slide_count), 0
                            ),
                            func.coalesce(func.sum(PresentationMetric.dwell_ms), 0),
                        )
                        .join(
                            ContentPresentation,
                            ContentPresentation.id
                            == PresentationMetric.presentation_id,
                        )
                        .join(
                            LearningSession,
                            LearningSession.id
                            == ContentPresentation.session_id,
                        )
                        .where(
                            ContentPresentation.lesson_version_slide_id == slide.id,
                            LearningSession.enrollment_id == enrollment.id,
                            PresentationMetric.algorithm_version
                            == DEFAULT_ALGORITHM_VERSION,
                        )
                    )
                ).one()
                total_samples += int(sample_count)
                on_slide_samples += int(on_slide_count)
                viewed = int(dwell_ms) > 0
                if slide.is_key and viewed:
                    key_done += 1
                if not slide.is_key and viewed:
                    normal_done += 1

            attention = (
                round(on_slide_samples / total_samples * 100, 1)
                if total_samples
                else None
            )
            key_ratio = key_done / key_total if key_total else None
            normal_ratio = normal_done / normal_total if normal_total else None
            if key_ratio is not None and normal_ratio is not None:
                mastery = round(100 * (0.85 * key_ratio + 0.15 * normal_ratio), 1)
            elif key_ratio is not None:
                mastery = round(100 * key_ratio, 1)
            elif normal_ratio is not None:
                mastery = round(100 * normal_ratio, 1)
            else:
                mastery = None
            lessons.append(
                StudentLessonOut(
                    lesson_id=lesson.id,
                    attention=attention,
                    mastery=mastery,
                    key_done=key_done,
                    key_total=key_total,
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
