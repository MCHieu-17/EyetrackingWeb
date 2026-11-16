"""Đánh giá geometry AOI giao diện trên snapshot layout.

`view_layouts.elements` lưu rect của mọi phần tử `[data-aoi]` tại thời điểm
ghi. Module này là nguồn duy nhất quy đổi geometry AOI UI (selector, anchor,
rect trực tiếp) thành rect cụ thể. Worker metrics và màn hình replay cùng dùng
một implementation để nhãn hiển thị khớp với nhãn đã lưu trong `gaze_samples`.
"""

from __future__ import annotations

import re

from app.models.aoi import Aoi

NO_LABEL_CODE = "no_label"
_SELECTOR_RE = re.compile(r"\[data-aoi=['\"]?([^'\"]+)['\"]?\]")


def inside(x: float, y: float, geometry: dict) -> bool:
    try:
        return (
            float(geometry["xMin"]) <= x <= float(geometry["xMax"])
            and float(geometry["yMin"]) <= y <= float(geometry["yMax"])
        )
    except (KeyError, TypeError, ValueError):
        return False


def area(geometry: dict) -> float:
    try:
        return max(
            0.0,
            (float(geometry["xMax"]) - float(geometry["xMin"]))
            * (float(geometry["yMax"]) - float(geometry["yMin"])),
        )
    except (KeyError, TypeError, ValueError):
        return 0.0


def elements_by_code(elements: list[dict]) -> dict[str, list[dict]]:
    """Gom mọi rect theo code; một code có thể có nhiều instance."""
    by_code: dict[str, list[dict]] = {}
    for element in elements:
        code = str(element.get("code") or element.get("semanticCode") or "")
        if not code:
            continue
        by_code.setdefault(code, []).append(element)
    return by_code


def rects_for(row: Aoi, rect_by_code: dict[str, list[dict]]) -> list[dict]:
    """Quy đổi geometry của một AOI UI thành danh sách rect cụ thể."""
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


def ui_aoi_label(
    x: float,
    y: float,
    aois: list[Aoi],
    elements: list[dict],
) -> str:
    """Một nhãn UI duy nhất: tên AOI cụ thể nhất hoặc UI_NO_LABEL."""
    rect_by_code = elements_by_code(elements)
    matches: list[tuple[int, float, str, str]] = []
    for row in aois:
        # Container chỉ gom nhóm; nhãn UI luôn lấy từ leaf cụ thể.
        if not row.is_active or row.is_container or row.code == NO_LABEL_CODE:
            continue
        for rect in rects_for(row, rect_by_code):
            if inside(x, y, rect):
                matches.append(
                    (
                        0 if row.kind == "custom" else 1,
                        area(rect),
                        row.code,
                        (row.name or "").strip(),
                    )
                )
    if not matches:
        return "UI_NO_LABEL"

    _, _, _, name = min(
        matches,
        key=lambda item: (item[0], item[1], item[2]),
    )
    return name or "UI_NO_LABEL"


def ui_regions(aois: list[Aoi], elements: list[dict]) -> list[dict]:
    """Trả rect cụ thể của từng AOI UI cho màn hình replay.

    Bao gồm cả AOI đang tắt để giáo viên thấy vùng đã bỏ đánh dấu; frontend
    quyết định làm mờ chúng. Container và no_label bị bỏ qua.
    """
    rect_by_code = elements_by_code(elements)
    out: list[dict] = []
    for row in aois:
        if row.is_container or row.code == NO_LABEL_CODE:
            continue
        rects = rects_for(row, rect_by_code)
        if not rects:
            continue
        out.append(
            {
                "code": row.code,
                "name": row.name,
                "kind": row.kind,
                "label": row.label,
                "is_active": row.is_active,
                "rects": rects,
            }
        )
    return out
