"""Tính gaze → tọa độ slide, AOI codes và metrics trong một lượt xem."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aoi import Aoi
from app.models.gaze import ContentView, GazeSample, ViewLayout

GRID_SIZE = 24
FIXATION_RADIUS = 0.03
MIN_FIXATION_POINTS = 2
MAX_GAP_MS = 250
ANALYSIS_VERSION = "gaze-metrics-v4"

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
_SELECTOR_RE = re.compile(r"\[data-aoi=['\"]?([^'\"]+)['\"]?\]")


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


def _inside(x: float, y: float, geometry: dict) -> bool:
    try:
        return (
            float(geometry["xMin"]) <= x <= float(geometry["xMax"])
            and float(geometry["yMin"]) <= y <= float(geometry["yMax"])
        )
    except (KeyError, TypeError, ValueError):
        return False


def _area(geometry: dict) -> float:
    try:
        return max(
            0.0,
            (float(geometry["xMax"]) - float(geometry["xMin"]))
            * (float(geometry["yMax"]) - float(geometry["yMin"])),
        )
    except (KeyError, TypeError, ValueError):
        return 0.0


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


def _elements_by_code(elements: list[dict]) -> dict[str, list[dict]]:
    """Gom mọi rect theo code; một code có thể có nhiều instance."""
    by_code: dict[str, list[dict]] = {}
    for element in elements:
        code = str(element.get("code") or element.get("semanticCode") or "")
        if not code:
            continue
        by_code.setdefault(code, []).append(element)
    return by_code


def _rects_for(
    row: Aoi, rect_by_code: dict[str, list[dict]]
) -> list[dict]:
    geometry = row.geometry or {}
    anchor = geometry.get("anchor")
    if anchor:
        rects: list[dict] = []
        for anchor_rect in rect_by_code.get(str(anchor), []):
            try:
                ax0 = float(anchor_rect["xMin"])
                ay0 = float(anchor_rect["yMin"])
                ax1 = float(anchor_rect["xMax"])
                ay1 = float(anchor_rect["yMax"])
                rects.append(
                    {
                        "xMin": ax0 + float(geometry["xMin"]) * (ax1 - ax0),
                        "yMin": ay0 + float(geometry["yMin"]) * (ay1 - ay0),
                        "xMax": ax0 + float(geometry["xMax"]) * (ax1 - ax0),
                        "yMax": ay0 + float(geometry["yMax"]) * (ay1 - ay0),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue
        return rects
    selector = str(geometry.get("selector") or "")
    match = _SELECTOR_RE.search(selector)
    if match:
        return list(rect_by_code.get(match.group(1), []))
    if "xMin" in geometry and "xMax" in geometry:
        return [geometry]
    return []


def _ui_aoi_label(
    x: float,
    y: float,
    aois: list[Aoi],
    elements: list[dict],
) -> str:
    """Một nhãn UI duy nhất: tên AOI cụ thể nhất hoặc UI_NO_LABEL."""
    rect_by_code = _elements_by_code(elements)
    matches: list[tuple[int, float, str, str]] = []
    for row in aois:
        if not row.is_active or row.code == NO_LABEL_CODE:
            continue
        for rect in _rects_for(row, rect_by_code):
            if _inside(x, y, rect):
                matches.append(
                    (
                        0 if row.kind == "custom" else 1,
                        _area(rect),
                        row.code,
                        (row.name or "").strip(),
                    )
                )
    if not matches:
        return UI_NO_LABEL

    _, _, _, name = min(
        matches,
        key=lambda item: (item[0], item[1], item[2]),
    )
    return name or UI_NO_LABEL


def _empty_grid() -> list[list[int]]:
    return [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]


def _grid_cell(x: float, y: float) -> tuple[int, int] | None:
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        return None
    return min(GRID_SIZE - 1, int(x * GRID_SIZE)), min(
        GRID_SIZE - 1, int(y * GRID_SIZE)
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


def _sample_coords(
    sample: GazeSample, layout: ViewLayout | None
) -> tuple[float, float] | None:
    """Chọn toạ độ gaze phù hợp với hệ toạ độ của layout.

    - original-v1: dùng original_viewport_x/y (viewport calibration).
    - current-v1: dùng viewport_x/y (viewport hiện tại) như dữ liệu cũ.
    - Client cũ thiếu original -> fallback viewport (raw calibration).
    """
    coordinate_space = layout.coordinate_space if layout else "current-v1"
    if coordinate_space == "original-v1":
        x = sample.original_viewport_x
        y = sample.original_viewport_y
        if x is None or y is None:
            x, y = sample.viewport_x, sample.viewport_y
    else:
        x, y = sample.viewport_x, sample.viewport_y
    if x is None or y is None:
        return None
    return float(x), float(y)


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

    samples = (
        await db.execute(
            select(GazeSample)
            .where(GazeSample.content_view_id == view.id)
            .order_by(GazeSample.event_time, GazeSample.sequence)
        )
    ).scalars().all()

    grid = _empty_grid()
    points: list[tuple[float, float]] = []
    gaze_count = 0
    on_slide_count = 0
    dwell_ms = 0
    previous_time: datetime | None = None
    previous_ok = False

    for sample in samples:
        gaze_count += 1
        is_ok = sample.status == "ok"
        layout = layout_by_id.get(sample.layout_id) if sample.layout_id else None
        layout = layout or default_layout
        has_layout = layout is not None and bool(layout.slide_rect)
        coords = _sample_coords(sample, layout) if is_ok else None
        mapped: tuple[float, float] | None = None

        if is_ok and coords is not None and not is_quiz:
            if has_layout:
                mapped = map_viewport_to_slide(
                    coords[0], coords[1], layout.slide_rect
                )
            else:
                quality = dict(sample.quality_flags or {})
                quality["layout_missing"] = True
                sample.quality_flags = quality

        elements = layout.elements if layout else []
        label: str | None = None
        if mapped is not None:
            x, y = mapped
            sample.slide_x = x
            sample.slide_y = y
            if _is_inside_slide(x, y):
                cell = _grid_cell(x, y)
                if cell is not None:
                    on_slide_count += 1
                    grid[cell[0]][cell[1]] += 1
                    points.append((x, y))
                label = _slide_aoi_label(x, y, slide_aois)
            else:
                label = _ui_aoi_label(
                    coords[0], coords[1], ui_aois, elements
                )
        elif is_ok:
            sample.slide_x = None
            sample.slide_y = None
            if coords is not None:
                label = _ui_aoi_label(
                    coords[0], coords[1], ui_aois, elements
                )
        else:
            sample.slide_x = None
            sample.slide_y = None

        # Một nhãn duy nhất mỗi sample. `aoi_codes` chỉ còn là legacy 0/1 phần tử.
        sample.aoi_label = label
        sample.aoi_codes = [label] if label else []

        if is_ok and previous_ok and previous_time is not None:
            delta = (sample.event_time - previous_time).total_seconds() * 1000
            if 0 <= delta <= MAX_GAP_MS:
                dwell_ms += int(delta)
        previous_time = sample.event_time
        previous_ok = is_ok

    view.gaze_count = gaze_count
    view.on_slide_gaze_count = on_slide_count
    view.tracked_duration_ms = dwell_ms
    view.fixation_count = _count_fixations(points)
    view.heatmap_grid = grid
    view.analysis_status = "ready"
    view.analysis_version = ANALYSIS_VERSION
    view.analyzed_at = _now()
    await db.flush()
    return view
