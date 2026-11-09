"""Metrics projection từ gaze_samples + presentation/layout.

Một nguồn gaze gốc; mọi dashboard đọc projection `presentation_metrics` hoặc
view SQL. Không giữ bảng aggregate legacy.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aoi import AoiLayoutSnapshot, PresentationMetric
from app.models.course import Course
from app.models.gaze import ContentPresentation, GazeBatch, GazeSample
from app.schemas.course import StudentRowOut
from app.services import course_students as course_students_service
from app.services.course_students import DEFAULT_ALGORITHM_VERSION

__all__ = [
    "DEFAULT_ALGORITHM_VERSION",
    "compute_presentation_metrics",
    "course_students",
    "refresh_session_metrics",
]

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
    return await course_students_service.course_students(db, course)
