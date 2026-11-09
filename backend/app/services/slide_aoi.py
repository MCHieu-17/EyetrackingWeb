"""Trích xuất vùng phân tích gợi ý từ trang PDF bằng PyMuPDF.

Kết quả chỉ là gợi ý: giáo viên luôn có thể đổi tên, xóa hoặc vẽ vùng khác.
Toạ độ được chuẩn hoá 0..1 theo `page.rect` (đã tính rotation) để khớp với
cách PDF.js hiển thị trang ở frontend.

Mỗi block text/image và mỗi bảng là một vùng riêng (không gộp union). Nhãn
tự động chỉ là loại vùng: `TEXT`, `IMAGE`, `TABLE`; giáo viên có thể đổi tên
sau. Text nằm đè lên ảnh vẫn được giữ; khi phân tích, TEXT được ưu tiên hơn
IMAGE.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pymupdf

# Tăng khi thay đổi cách sinh gợi ý để bỏ cache `render_metadata` cũ.
AOI_LAYOUT_VERSION = 4

MAX_AOIS_PER_SLIDE = 30
MIN_AREA_RATIO = 0.003
MAX_AREA_RATIO = 0.95
MIN_IMAGE_AREA_RATIO = 0.005
OVERLAP_SKIP_RATIO = 0.8
MERGE_OVERLAP_RATIO = 0.5

_WHITESPACE = re.compile(r"\s+")
_LEADING_BULLET = re.compile(r"^[\s•·▪◦\-–—*]+")
_PAGE_NUMBER = re.compile(r"^(trang|page)?\s*\d+$", re.IGNORECASE)


@dataclass(frozen=True)
class ExtractedAoi:
    code: str
    name: str
    kind: str
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "kind": self.kind,
            "xMin": round(self.x_min, 6),
            "yMin": round(self.y_min, 6),
            "xMax": round(self.x_max, 6),
            "yMax": round(self.y_max, 6),
        }


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _normalize_bbox(
    bbox: tuple[float, float, float, float],
    page: pymupdf.Page,
) -> tuple[float, float, float, float] | None:
    rect = pymupdf.Rect(bbox)
    if page.rotation:
        rect = rect * page.rotation_matrix
    page_rect = page.rect
    if page_rect.width <= 0 or page_rect.height <= 0:
        return None
    x_min = _clamp((rect.x0 - page_rect.x0) / page_rect.width)
    y_min = _clamp((rect.y0 - page_rect.y0) / page_rect.height)
    x_max = _clamp((rect.x1 - page_rect.x0) / page_rect.width)
    y_max = _clamp((rect.y1 - page_rect.y0) / page_rect.height)
    if x_max <= x_min or y_max <= y_min:
        return None
    return x_min, y_min, x_max, y_max


def _area(rect: tuple[float, float, float, float]) -> float:
    return max(0.0, rect[2] - rect[0]) * max(0.0, rect[3] - rect[1])


def _intersection_ratio(
    inner: tuple[float, float, float, float],
    outer: tuple[float, float, float, float],
) -> float:
    inner_area = _area(inner)
    if inner_area <= 0:
        return 0.0
    x0 = max(inner[0], outer[0])
    y0 = max(inner[1], outer[1])
    x1 = min(inner[2], outer[2])
    y1 = min(inner[3], outer[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return ((x1 - x0) * (y1 - y0)) / inner_area


def _clean_text(text: str) -> str:
    text = _WHITESPACE.sub(" ", text).strip()
    text = _LEADING_BULLET.sub("", text).strip()
    return text


def _is_meaningful(
    rect: tuple[float, float, float, float],
    *,
    min_ratio: float = MIN_AREA_RATIO,
) -> bool:
    # `rect` đã chuẩn hoá 0..1 nên diện tích của nó chính là tỉ lệ diện tích trang.
    area = _area(rect)
    if area <= 0:
        return False
    return min_ratio <= area <= MAX_AREA_RATIO


def _reading_order(
    items: list[ExtractedAoi],
    page_height: float,
) -> list[ExtractedAoi]:
    tolerance = page_height * 0.02

    def key(item: ExtractedAoi) -> tuple[float, float]:
        row = round(item.y_min / tolerance) if tolerance > 0 else 0
        return row, item.x_min

    return sorted(items, key=key)


def extract_page_aois(page: pymupdf.Page, slide_number: int) -> list[ExtractedAoi]:
    """Trả về danh sách vùng gợi ý cho một trang PDF.

    Mỗi text block, image block và bảng là một vùng riêng. Nhãn tự động là
    `TEXT`, `IMAGE`, `TABLE`; code vẫn đánh số theo loại để không trùng.
    """
    page_rect = page.rect
    page_area = page_rect.width * page_rect.height
    if page_area <= 0:
        return []

    tables: list[tuple[float, float, float, float]] = []
    images: list[tuple[float, float, float, float]] = []
    texts: list[tuple[float, float, float, float, str]] = []

    # 1) Bảng: giữ nguyên cả bảng là một vùng, không tách từng ô.
    try:
        finder = page.find_tables()
        for table in finder.tables:
            rect = _normalize_bbox(tuple(table.bbox), page)
            if rect is None or not _is_meaningful(
                rect, min_ratio=MIN_IMAGE_AREA_RATIO
            ):
                continue
            tables.append(rect)
    except Exception:  # noqa: BLE001 - table detection là best-effort
        tables = []

    # 2) Text + image blocks.
    try:
        text_dict = page.get_text("dict")
    except Exception:  # noqa: BLE001
        text_dict = {"blocks": []}

    for block in text_dict.get("blocks", []):
        bbox = block.get("bbox")
        if not bbox:
            continue
        rect = _normalize_bbox(tuple(bbox), page)
        if rect is None:
            continue
        if block.get("type") == 1:
            if not _is_meaningful(rect, min_ratio=MIN_IMAGE_AREA_RATIO):
                continue
            if any(
                _intersection_ratio(rect, table) > OVERLAP_SKIP_RATIO
                for table in tables
            ):
                continue
            images.append(rect)
            continue
        if block.get("type") != 0:
            continue
        if not _is_meaningful(rect):
            continue
        if any(
            _intersection_ratio(rect, table) > OVERLAP_SKIP_RATIO
            for table in tables
        ):
            continue
        # Không bỏ text nằm đè lên ảnh: analysis sẽ ưu tiên TEXT.
        text = " ".join(
            span.get("text", "")
            for line in block.get("lines", [])
            for span in line.get("spans", [])
        )
        clean = _clean_text(text)
        if len(clean) < 2 or _PAGE_NUMBER.match(clean):
            continue
        texts.append((*rect, clean))

    # 3) Loại trùng trong cùng nhóm (giữ vùng lớn hơn).
    def dedupe(
        rects: list[tuple[float, float, float, float]],
    ) -> list[tuple[float, float, float, float]]:
        kept: list[tuple[float, float, float, float]] = []
        for rect in sorted(rects, key=_area, reverse=True):
            if any(
                _intersection_ratio(rect, other) > OVERLAP_SKIP_RATIO
                for other in kept
            ):
                continue
            kept.append(rect)
        return kept

    tables = dedupe(tables)
    images = dedupe(images)

    text_kept: list[tuple[float, float, float, float, str]] = []
    for rect in sorted(texts, key=lambda item: _area(item[:4]), reverse=True):
        if any(
            _intersection_ratio(rect[:4], other[:4]) > OVERLAP_SKIP_RATIO
            for other in text_kept
        ):
            continue
        text_kept.append(rect)

    candidates: list[ExtractedAoi] = []
    for rect in tables:
        candidates.append(
            ExtractedAoi(
                code="",
                name="",
                kind="table",
                x_min=rect[0],
                y_min=rect[1],
                x_max=rect[2],
                y_max=rect[3],
            )
        )
    for rect in images:
        candidates.append(
            ExtractedAoi(
                code="",
                name="",
                kind="image",
                x_min=rect[0],
                y_min=rect[1],
                x_max=rect[2],
                y_max=rect[3],
            )
        )
    for x_min, y_min, x_max, y_max, text in text_kept:
        candidates.append(
            ExtractedAoi(
                code="",
                name="",
                kind="text",
                x_min=x_min,
                y_min=y_min,
                x_max=x_max,
                y_max=y_max,
                text=text,
            )
        )

    # 4) Giới hạn số vùng để danh sách không quá dài.
    if len(candidates) > MAX_AOIS_PER_SLIDE:
        candidates = sorted(
            candidates,
            key=lambda item: _area(
                (item.x_min, item.y_min, item.x_max, item.y_max)
            ),
            reverse=True,
        )[:MAX_AOIS_PER_SLIDE]

    # 5) Đánh số theo thứ tự đọc; nhãn chỉ là loại vùng.
    ordered = _reading_order(candidates, page_rect.height)
    counters: dict[str, int] = {}
    result: list[ExtractedAoi] = []
    for item in ordered:
        counters[item.kind] = counters.get(item.kind, 0) + 1
        index = counters[item.kind]
        if item.kind == "text":
            name = "TEXT"
        elif item.kind == "image":
            name = "IMAGE"
        elif item.kind == "table":
            name = "TABLE"
        else:
            name = "Vùng"
        result.append(
            ExtractedAoi(
                code=f"slide_{slide_number}_{item.kind}_{index}",
                name=name,
                kind=item.kind,
                x_min=item.x_min,
                y_min=item.y_min,
                x_max=item.x_max,
                y_max=item.y_max,
                text=item.text,
            )
        )
    return result


def extract_document_aois(pdf_bytes: bytes) -> dict[int, list[dict[str, Any]]]:
    """Trả về {page_number (1-based): [candidate dict]} cho toàn bộ PDF."""
    result: dict[int, list[dict[str, Any]]] = {}
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            page_number = page_index + 1
            try:
                candidates = extract_page_aois(page, page_number)
            except Exception:  # noqa: BLE001 - một trang lỗi không chặn cả tài liệu
                candidates = []
            result[page_number] = [item.to_dict() for item in candidates]
    return result


def extract_page_from_pdf(
    pdf_bytes: bytes, page_number: int
) -> list[dict[str, Any]]:
    """Trích xuất gợi ý cho đúng một trang (dùng cho slide cũ chưa cache)."""
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
        if page_number < 1 or page_number > document.page_count:
            return []
        page = document.load_page(page_number - 1)
        return [item.to_dict() for item in extract_page_aois(page, page_number)]


def candidates_from_metadata(metadata: dict | None) -> list[dict[str, Any]]:
    if not isinstance(metadata, dict):
        return []
    if metadata.get("aoi_layout_version") != AOI_LAYOUT_VERSION:
        return []
    raw = metadata.get("aoi_candidates")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            out.append(
                {
                    "code": str(item["code"]),
                    "name": str(item["name"]),
                    "kind": str(item.get("kind") or "custom"),
                    "xMin": float(item["xMin"]),
                    "yMin": float(item["yMin"]),
                    "xMax": float(item["xMax"]),
                    "yMax": float(item["yMax"]),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


def next_code(existing_codes: set[str], slide_number: int, kind: str) -> str:
    index = 1
    while True:
        code = f"slide_{slide_number}_{kind}_{index}"
        if code not in existing_codes:
            return code
        index += 1


def overlaps_existing(
    candidate: dict[str, Any],
    existing: list[dict[str, Any]],
) -> bool:
    rect = (
        float(candidate["xMin"]),
        float(candidate["yMin"]),
        float(candidate["xMax"]),
        float(candidate["yMax"]),
    )
    for item in existing:
        geometry = item.get("geometry") or {}
        try:
            other = (
                float(geometry["xMin"]),
                float(geometry["yMin"]),
                float(geometry["xMax"]),
                float(geometry["yMax"]),
            )
        except (KeyError, TypeError, ValueError):
            continue
        if _intersection_ratio(rect, other) > MERGE_OVERLAP_RATIO:
            return True
    return False
