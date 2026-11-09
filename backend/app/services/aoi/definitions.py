"""AOI definition serialization, validation, and persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aoi import AoiDefinition, AoiSet
from app.schemas.aoi import AoiDefinitionIn, AoiDefinitionOut, AoiSetOut

from .common import NO_LABEL_CODE, NO_LABEL_NAME, _bad_request


def _definition_out(row: AoiDefinition) -> AoiDefinitionOut:
    return AoiDefinitionOut(
        id=row.id,
        code=row.code,
        name=row.name,
        parent_id=row.parent_id,
        geometry=row.geometry or {},
        is_container=row.is_container,
        kind=row.kind,
        is_active=row.is_active,
    )


def _set_out(row: AoiSet, definitions: list[AoiDefinition]) -> AoiSetOut:
    return AoiSetOut(
        id=row.id,
        scope=row.scope,
        slide_version_id=row.slide_version_id,
        ui_schema_version=row.ui_schema_version,
        revision=row.revision,
        state=row.state,
        created_by=row.created_by,
        created_at=row.created_at,
        published_at=row.published_at,
        definitions=[_definition_out(item) for item in definitions],
    )


def _definition_to_input(row: AoiDefinition) -> AoiDefinitionIn:
    return AoiDefinitionIn(
        code=row.code,
        name=row.name,
        parent_id=row.parent_id,
        geometry=row.geometry or {},
        is_container=row.is_container,
        kind=row.kind,
        is_active=row.is_active,
    )


def _definition_to_input_with_codes(
    row: AoiDefinition, code_by_id: dict[str, str]
) -> AoiDefinitionIn:
    """Chuyển definition sang input, đổi parent_id (UUID) thành code.

    `_replace_definitions` xoá rồi tạo lại toàn bộ definition nên ID cha cũ
    không còn tồn tại; `_insert_definitions` chỉ tìm được cha theo code.
    """
    return AoiDefinitionIn(
        code=row.code,
        name=row.name,
        parent_id=code_by_id.get(row.parent_id) if row.parent_id else None,
        geometry=row.geometry or {},
        is_container=row.is_container,
        kind=row.kind,
        is_active=row.is_active,
    )


def _validate_rect(geometry: dict) -> None:
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


def _validate_geometry(
    scope: str, code: str, geometry: dict, is_container: bool
) -> None:
    if not isinstance(geometry, dict):
        raise _bad_request("geometry phải là object")
    if code == NO_LABEL_CODE:
        return
    if scope == "slide":
        _validate_rect(geometry)
        return

    anchor = geometry.get("anchor")
    selector = geometry.get("selector")
    if anchor is not None:
        if not isinstance(anchor, str) or not anchor.strip():
            raise _bad_request("anchor phải là chuỗi")
        _validate_rect(geometry)
        return
    if selector is not None:
        if not isinstance(selector, str):
            raise _bad_request("selector phải là chuỗi")
        return
    if is_container:
        return
    raise _bad_request("Vùng giao diện cần selector hoặc anchor + rect")


async def _definitions(db: AsyncSession, set_id: str) -> list[AoiDefinition]:
    return list(
        (
            await db.execute(
                select(AoiDefinition)
                .where(AoiDefinition.aoi_set_id == set_id)
                .order_by(AoiDefinition.code)
            )
        )
        .scalars()
        .all()
    )


async def ensure_no_label_definition(db: AsyncSession, set_id: str) -> None:
    existing = (
        await db.execute(
            select(AoiDefinition).where(
                AoiDefinition.aoi_set_id == set_id,
                AoiDefinition.code == NO_LABEL_CODE,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return
    db.add(
        AoiDefinition(
            aoi_set_id=set_id,
            code=NO_LABEL_CODE,
            name=NO_LABEL_NAME,
            parent_id=None,
            geometry={},
            is_container=False,
            kind="system",
            is_active=True,
        )
    )
    await db.flush()


async def _insert_definitions(
    db: AsyncSession, set_id: str, definitions: list[AoiDefinitionIn], scope: str
) -> None:
    by_code: dict[str, AoiDefinition] = {}
    for item in definitions:
        if item.code == NO_LABEL_CODE:
            continue
        _validate_geometry(scope, item.code, item.geometry, item.is_container)
        if item.code in by_code:
            raise _bad_request(f"Mã vùng bị trùng: {item.code}")
        row = AoiDefinition(
            aoi_set_id=set_id,
            code=item.code,
            name=item.name,
            parent_id=None,
            geometry=item.geometry,
            is_container=item.is_container,
            kind=item.kind,
            is_active=item.is_active,
        )
        db.add(row)
        await db.flush()
        by_code[item.code] = row

    for item in definitions:
        if item.code == NO_LABEL_CODE:
            continue
        if not item.parent_id:
            continue
        parent = by_code.get(item.parent_id)
        if parent is None:
            parent = await db.get(AoiDefinition, item.parent_id)
            if parent is not None and parent.aoi_set_id != set_id:
                # Client gửi ID của bản cũ (trước khi clone revision): tìm lại
                # theo code trong bộ vùng hiện tại.
                parent = by_code.get(parent.code)
            if parent is None or parent.aoi_set_id != set_id:
                raise _bad_request("Vùng cha phải thuộc cùng bộ vùng")
        by_code[item.code].parent_id = parent.id

    # Vùng có con luôn là container, kể cả khi client quên đánh dấu.
    for row in by_code.values():
        if any(child.parent_id == row.id for child in by_code.values()):
            row.is_container = True

    await ensure_no_label_definition(db, set_id)


async def _replace_definitions(
    db: AsyncSession,
    set_id: str,
    definitions: list[AoiDefinitionIn],
    scope: str,
) -> None:
    existing = await _definitions(db, set_id)
    for item in existing:
        await db.delete(item)
    await db.flush()
    await _insert_definitions(db, set_id, definitions, scope)
