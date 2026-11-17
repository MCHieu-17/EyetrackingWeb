"""AOI serialization, validation and persistence."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aoi import Aoi
from app.schemas.aoi import AoiCollectionOut, AoiDefinitionIn, AoiDefinitionOut

from .common import NO_LABEL_CODE, NO_LABEL_NAME, _bad_request

# Nhãn slide do giáo viên đặt: AOI_1, AOI_THANHCHAT, AOI_BANGBIEU...
# Tổng độ dài tối đa 64 ký tự, đúng với cột aois.label.
_SLIDE_LABEL_RE = re.compile(r"^AOI_[A-Z0-9_]{1,60}$")
# Nhãn số tự động (AOI_n) dùng để cấp số kế tiếp, không đụng nhãn giáo viên.
_AUTO_SLIDE_LABEL_RE = re.compile(r"^AOI_([1-9]\d*)$")


def _next_slide_label(used: set[str]) -> str:
    numbers: list[int] = []
    for label in used:
        match = _AUTO_SLIDE_LABEL_RE.match(label)
        if match:
            numbers.append(int(match.group(1)))
    return f"AOI_{max(numbers, default=0) + 1}"


def _normalize_slide_label(label: str | None) -> str | None:
    clean = (label or "").strip().upper()
    return clean or None

def _definition_out(row: Aoi) -> AoiDefinitionOut:
    return AoiDefinitionOut(
        id=row.id,
        code=row.code,
        name=row.name,
        label=row.label,
        parent_id=row.parent_id,
        geometry=row.geometry or {},
        is_container=row.is_container,
        kind=row.kind,
        is_active=row.is_active,
    )


def aoi_collection_out(
    *,
    scope: str,
    slide_id: str | None,
    ui_schema: str | None,
    definitions: list[Aoi],
) -> AoiCollectionOut:
    return AoiCollectionOut(
        id=slide_id or (f"ui:{ui_schema}" if ui_schema else ""),
        scope=scope,
        slide_id=slide_id,
        ui_schema=ui_schema,
        definitions=[_definition_out(item) for item in definitions],
    )


def definition_to_input(row: Aoi) -> AoiDefinitionIn:
    return AoiDefinitionIn(
        code=row.code,
        name=row.name,
        label=row.label,
        parent_id=row.parent_id,
        geometry=row.geometry or {},
        is_container=row.is_container,
        kind=row.kind,
        is_active=row.is_active,
    )


def _validate_geometry(scope: str, code: str, geometry: dict, is_container: bool) -> None:
    if not isinstance(geometry, dict):
        raise _bad_request("geometry phải là object")
    if code == NO_LABEL_CODE:
        return
    if scope == "slide":
        keys = ("xMin", "yMin", "xMax", "yMax")
        if not all(key in geometry for key in keys):
            raise _bad_request("Vùng cần xMin/yMin/xMax/yMax")
        try:
            x_min = float(geometry["xMin"])
            y_min = float(geometry["yMin"])
            x_max = float(geometry["xMax"])
            y_max = float(geometry["yMax"])
        except (TypeError, ValueError) as exc:
            raise _bad_request("Toạ độ vùng phải là số") from exc
        if not (0.0 <= x_min < x_max <= 1.0 and 0.0 <= y_min < y_max <= 1.0):
            raise _bad_request("Toạ độ vùng phải trong [0,1] và min < max")
        return

    anchor = geometry.get("anchor")
    selector = geometry.get("selector")
    if anchor is not None:
        if not isinstance(anchor, str) or not anchor.strip():
            raise _bad_request("anchor phải là chuỗi")
        return
    if selector is not None:
        if not isinstance(selector, str):
            raise _bad_request("selector phải là chuỗi")
        return
    if is_container:
        return
    raise _bad_request("Vùng giao diện cần selector hoặc anchor + rect")


async def load_aois(
    db: AsyncSession, *, slide_id: str | None = None, ui_schema: str | None = None
) -> list[Aoi]:
    stmt = select(Aoi).order_by(Aoi.code)
    if slide_id is not None:
        stmt = stmt.where(Aoi.slide_id == slide_id)
    if ui_schema is not None:
        stmt = stmt.where(Aoi.ui_schema == ui_schema)
    return list((await db.execute(stmt)).scalars().all())


async def replace_aois(
    db: AsyncSession,
    *,
    scope: str,
    slide_id: str | None,
    ui_schema: str | None,
    definitions: list[AoiDefinitionIn],
) -> list[Aoi]:
    existing = await load_aois(db, slide_id=slide_id, ui_schema=ui_schema)
    old_code_by_id = {item.id: item.code for item in existing}
    old_label_by_code = {item.code: item.label for item in existing}

    seen_codes: set[str] = set()
    seen_ui_names: set[str] = set()
    for item in definitions:
        if item.code == NO_LABEL_CODE:
            continue
        if item.code in seen_codes:
            raise _bad_request(f"Mã vùng bị trùng: {item.code}")
        seen_codes.add(item.code)
        _validate_geometry(scope, item.code, item.geometry, item.is_container)
        if scope == "ui" and not item.is_container:
            normalized = item.name.strip().casefold()
            if not normalized:
                raise _bad_request("Tên vùng giao diện không được để trống")
            if normalized.startswith("slide_") or normalized == "ui_no_label":
                raise _bad_request(
                    "Tên vùng giao diện không được trùng tiền tố SLIDE_/UI_NO_LABEL"
                )
            if normalized in seen_ui_names:
                raise _bad_request(
                    f"Tên vùng giao diện bị trùng: {item.name.strip()}"
                )
            seen_ui_names.add(normalized)

    used_labels: set[str] = set()
    labels_by_code: dict[str, str | None] = {}
    for item in definitions:
        if (
            scope != "slide"
            or item.code == NO_LABEL_CODE
            or item.is_container
        ):
            labels_by_code[item.code] = None
            continue
        label = _normalize_slide_label(item.label)
        if label is not None and not _SLIDE_LABEL_RE.match(label):
            raise _bad_request(f"Nhãn vùng slide không hợp lệ: {item.label}")
        if label is not None and label in used_labels:
            raise _bad_request(f"Nhãn vùng slide bị trùng: {label}")
        if label is None:
            old = old_label_by_code.get(item.code)
            label = (
                old
                if old
                and _SLIDE_LABEL_RE.match(old)
                and old not in used_labels
                else None
            )
        if label is None:
            label = _next_slide_label(used_labels)
        used_labels.add(label)
        labels_by_code[item.code] = label

    for item in existing:
        await db.delete(item)
    await db.flush()

    by_code: dict[str, Aoi] = {}
    for item in definitions:
        if item.code == NO_LABEL_CODE:
            continue
        row = Aoi(
            slide_id=slide_id,
            ui_schema=ui_schema,
            code=item.code,
            name=item.name,
            label=labels_by_code.get(item.code),
            geometry=item.geometry,
            is_container=item.is_container,
            kind=item.kind,
            is_active=item.is_active,
        )
        db.add(row)
        await db.flush()
        by_code[item.code] = row

    for item in definitions:
        if item.code == NO_LABEL_CODE or not item.parent_id:
            continue
        parent_code = old_code_by_id.get(item.parent_id, item.parent_id)
        parent = by_code.get(parent_code)
        if parent is None:
            continue
        by_code[item.code].parent_id = parent.id

    for row in by_code.values():
        if any(child.parent_id == row.id for child in by_code.values()):
            row.is_container = True

    if NO_LABEL_CODE not in by_code:
        db.add(
            Aoi(
                slide_id=slide_id,
                ui_schema=ui_schema,
                code=NO_LABEL_CODE,
                name=NO_LABEL_NAME,
                geometry={},
                is_container=False,
                kind="system",
                is_active=True,
            )
        )
    await db.flush()
    return await load_aois(db, slide_id=slide_id, ui_schema=ui_schema)
