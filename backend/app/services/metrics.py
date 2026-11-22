"""Tính gaze → tọa độ slide, nhãn AOI và metrics trong một lượt xem."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone

from sqlalchemy import (
    REAL,
    BigInteger,
    Text,
    bindparam,
    func,
    select,
    text,
    tuple_,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.aoi import Aoi
from app.models.gaze import ContentView, GazeSample, ViewLayout
from app.services import aoi_regions

_area = aoi_regions.area
_inside = aoi_regions.inside
_ui_aoi_label = aoi_regions.ui_aoi_label

GRID_SIZE = 24
FIXATION_RADIUS = 0.03
MIN_FIXATION_POINTS = 2
ANALYSIS_VERSION = "gaze-metrics-v8"
# Mỗi lô sample được đọc/ghi/commit riêng để transaction của worker bị chặn
# trên vài nghìn row thay vì toàn bộ lượt xem.
SAMPLE_CHUNK_SIZE = 3000

_SAMPLE_UPDATE_SQL = text(
    """
    UPDATE gaze_samples AS gs
    SET slide_x = v.slide_x,
        slide_y = v.slide_y,
        aoi_label = v.aoi_label,
        quality_flags = v.quality_flags
    FROM unnest(
        CAST(:ids AS BIGINT[]),
        CAST(:slide_xs AS REAL[]),
        CAST(:slide_ys AS REAL[]),
        CAST(:labels AS TEXT[]),
        CAST(:flags AS JSONB[])
    ) AS v(id, slide_x, slide_y, aoi_label, quality_flags)
    WHERE gs.id = v.id
    """
).bindparams(
    bindparam("ids", type_=ARRAY(BigInteger)),
    bindparam("slide_xs", type_=ARRAY(REAL)),
    bindparam("slide_ys", type_=ARRAY(REAL)),
    bindparam("labels", type_=ARRAY(Text)),
    bindparam("flags", type_=ARRAY(JSONB)),
)

# Ghi metrics một lần, chỉ khi không có sample mới hơn snapshot. Điều kiện
# NOT EXISTS chạy trong cùng statement nên không đè `pending` do batch gaze
# vừa commit trong lúc worker đang phân tích.
_VIEW_UPDATE_SQL = text(
    """
    UPDATE content_views
    SET gaze_count = :gaze_count,
        on_slide_gaze_count = :on_slide_gaze_count,
        tracked_duration_ms = :tracked_duration_ms,
        fixation_count = :fixation_count,
        heatmap_grid = CAST(:heatmap_grid AS JSONB),
        aoi_stats = CAST(:aoi_stats AS JSONB),
        analysis_status = 'ready',
        analysis_version = :analysis_version,
        analyzed_at = :analyzed_at
    WHERE id = :view_id
      AND NOT EXISTS (
          SELECT 1
          FROM gaze_samples
          WHERE content_view_id = :view_id
            AND id > CAST(:max_id AS BIGINT)
      )
    """
)

SLIDE_LABEL_PREFIX = "SLIDE_"
SLIDE_NO_LABEL = "SLIDE_NO_LABEL"
UI_NO_LABEL = "UI_NO_LABEL"
NO_LABEL_CODE = "no_label"
_SLIDE_LABEL_INVALID = re.compile(r"[^A-Z0-9_]+")

_KIND_PRIORITY = {
    "custom": 1,
    "text": 2,
    "table": 3,
    "image": 4,
    "drawing": 5,
    "system": 6,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def map_viewport_to_slide(
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


def _is_inside_slide(x: float, y: float) -> bool:
    return 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0


def _slide_label_text(label: str | None, code: str) -> str:
    raw = (label or code or "").strip().upper()
    ascii_text = (
        unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    )
    clean = _SLIDE_LABEL_INVALID.sub("_", ascii_text).strip("_")
    return clean or "AOI"


def _slide_aoi_label(x: float, y: float, aois: list[Aoi]) -> str:
    """Một nhãn slide duy nhất: SLIDE_<label> hoặc SLIDE_NO_LABEL."""
    if not _is_inside_slide(x, y):
        return SLIDE_NO_LABEL

    leaves = [
        row
        for row in aois
        if not row.is_container
        and row.is_active
        and row.code != NO_LABEL_CODE
        and _inside(x, y, row.geometry or {})
    ]
    if not leaves:
        return SLIDE_NO_LABEL

    best = min(
        leaves,
        key=lambda row: (
            _KIND_PRIORITY.get(row.kind, 9),
            _area(row.geometry or {}),
            row.code,
        ),
    )
    return f"{SLIDE_LABEL_PREFIX}{_slide_label_text(best.label, best.code)}"


def _empty_grid() -> list[list[int]]:
    return [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]


def _grid_cell(x: float, y: float) -> tuple[int, int] | None:
    """Trả (row, col) row-major để khớp `heatmap_grid[y][x]`."""
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        return None
    return (
        min(GRID_SIZE - 1, int(y * GRID_SIZE)),
        min(GRID_SIZE - 1, int(x * GRID_SIZE)),
    )


def _count_fixations(points: list[tuple[float, float]]) -> int:
    fixations = count = 0
    sum_x = sum_y = 0.0
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


async def analyze_content_view(db: AsyncSession, view_id: str) -> ContentView:
    view = await db.get(ContentView, view_id)
    if view is None:
        raise ValueError("content view not found")

    layouts = (
        await db.execute(
            select(ViewLayout)
            .where(ViewLayout.content_view_id == view.id)
            .order_by(ViewLayout.captured_at)
        )
    ).scalars().all()
    default_layout = layouts[-1] if layouts else None
    layout_by_id = {layout.id: layout for layout in layouts}

    is_quiz = view.surface == "quiz" or view.slide_id is None
    slide_aois = (
        (
            await db.execute(
                select(Aoi).where(Aoi.slide_id == view.slide_id)
            )
        ).scalars().all()
        if view.slide_id and not is_quiz
        else []
    )
    ui_aois = (
        await db.execute(select(Aoi).where(Aoi.ui_schema == "reader-v1"))
    ).scalars().all()

    max_id = (
        await db.execute(
            select(func.max(GazeSample.id)).where(
                GazeSample.content_view_id == view.id
            )
        )
    ).scalar_one_or_none()

    grid = _empty_grid()
    points: list[tuple[float, float]] = []
    gaze_count = 0
    on_slide_count = 0
    dwell_ms = 0
    # Đọc một lần trước vòng lặp: ngưỡng gap phụ thuộc GAZE_FPS.
    max_gap_ms = settings.gaze_max_gap_ms
    # Thống kê dẫn xuất cho dashboard: {label: {"ms": int, "samples": int}}.
    aoi_stats: dict[str, dict[str, int]] = {}
    previous_time: datetime | None = None
    previous_ok = False
    last_time: datetime | None = None
    last_sequence = 0
    last_id = 0

    while max_id is not None:
        stmt = select(
            GazeSample.id,
            GazeSample.layout_id,
            GazeSample.event_time,
            GazeSample.sequence,
            GazeSample.viewport_x,
            GazeSample.viewport_y,
            GazeSample.status,
            GazeSample.quality_flags,
        ).where(
            GazeSample.content_view_id == view.id,
            GazeSample.id <= max_id,
        )
        if last_time is not None:
            stmt = stmt.where(
                tuple_(
                    GazeSample.event_time,
                    GazeSample.sequence,
                    GazeSample.id,
                )
                > (last_time, last_sequence, last_id)
            )
        rows = (
            await db.execute(
                stmt.order_by(
                    GazeSample.event_time, GazeSample.sequence, GazeSample.id
                ).limit(SAMPLE_CHUNK_SIZE)
            )
        ).all()
        if not rows:
            break

        updates: list[tuple[int, float | None, float | None, str | None, dict]] = []
        for sample in rows:
            gaze_count += 1
            is_ok = sample.status == "ok"
            layout = layout_by_id.get(sample.layout_id) if sample.layout_id else None
            layout = layout or default_layout
            has_layout = layout is not None and bool(layout.slide_rect)
            coords = (
                (float(sample.viewport_x), float(sample.viewport_y))
                if is_ok
                and sample.viewport_x is not None
                and sample.viewport_y is not None
                else None
            )
            mapped: tuple[float, float] | None = None
            quality = sample.quality_flags or {}

            if is_ok and coords is not None and not is_quiz:
                if has_layout:
                    mapped = map_viewport_to_slide(
                        coords[0], coords[1], layout.slide_rect
                    )
                else:
                    quality = dict(quality)
                    quality["layout_missing"] = True

            elements = layout.elements if layout else []
            label: str | None = None
            slide_x: float | None = None
            slide_y: float | None = None
            if mapped is not None:
                slide_x, slide_y = mapped
                if _is_inside_slide(slide_x, slide_y):
                    cell = _grid_cell(slide_x, slide_y)
                    if cell is not None:
                        on_slide_count += 1
                        # cell = (row, col) nên `heatmap_grid[row][col]` là row-major `grid[y][x]`.
                        grid[cell[0]][cell[1]] += 1
                        points.append((slide_x, slide_y))
                    label = _slide_aoi_label(slide_x, slide_y, slide_aois)
                else:
                    label = _ui_aoi_label(
                        coords[0], coords[1], ui_aois, elements
                    )
            elif is_ok and coords is not None:
                label = _ui_aoi_label(
                    coords[0], coords[1], ui_aois, elements
                )

            # Một nhãn duy nhất mỗi sample: slide (SLIDE_*) hoặc UI (tên AOI).
            updates.append((sample.id, slide_x, slide_y, label, quality))

            if is_ok and label is not None:
                stats = aoi_stats.setdefault(label, {"ms": 0, "samples": 0})
                stats["samples"] += 1

            if is_ok and previous_ok and previous_time is not None:
                delta = (sample.event_time - previous_time).total_seconds() * 1000
                if 0 <= delta <= max_gap_ms:
                    elapsed = int(delta)
                    dwell_ms += elapsed
                    if label is not None:
                        stats = aoi_stats.setdefault(
                            label, {"ms": 0, "samples": 0}
                        )
                        stats["ms"] += elapsed
            previous_time = sample.event_time
            previous_ok = is_ok

        await db.execute(
            _SAMPLE_UPDATE_SQL,
            {
                "ids": [row[0] for row in updates],
                "slide_xs": [row[1] for row in updates],
                "slide_ys": [row[2] for row in updates],
                "labels": [row[3] for row in updates],
                "flags": [row[4] or {} for row in updates],
            },
        )
        await db.commit()

        last_time = rows[-1].event_time
        last_sequence = rows[-1].sequence
        last_id = rows[-1].id
        if len(rows) < SAMPLE_CHUNK_SIZE:
            break

    # Câu UPDATE tự bỏ qua nếu có sample mới hơn snapshot, nên view giữ
    # `pending` và job kế tiếp sẽ phân tích lại.
    await db.execute(
        _VIEW_UPDATE_SQL,
        {
            "gaze_count": gaze_count,
            "on_slide_gaze_count": on_slide_count,
            "tracked_duration_ms": dwell_ms,
            "fixation_count": _count_fixations(points),
            "heatmap_grid": json.dumps(grid),
            "aoi_stats": json.dumps(aoi_stats, ensure_ascii=False),
            "analysis_version": ANALYSIS_VERSION,
            "analyzed_at": _now(),
            "view_id": view.id,
            "max_id": max_id,
        },
    )
    await db.commit()
    await db.refresh(view)
    return view
