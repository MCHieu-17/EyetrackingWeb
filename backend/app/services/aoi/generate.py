"""AOI generation from slide PDF candidates and UI components."""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.media import MediaAsset
from app.schemas.aoi import (
    AoiCollectionOut,
    AoiDefinitionIn,
    AoiGenerateIn,
    AoiUiGenerateIn,
)
from app.services import media_storage, slide_aoi

from .access import require_slide_manage, require_ui_manage, slide_with_course
from .common import NO_LABEL_CODE
from .definitions import (
    _next_slide_label,
    aoi_collection_out,
    definition_to_input,
    load_aois,
    replace_aois,
)

AUTO_KINDS = {"text", "image", "table"}


def _build_generated(
    slide_number: int,
    candidates: list[dict],
    existing: list[AoiDefinitionIn],
) -> list[AoiDefinitionIn]:
    root_code = f"slide_{slide_number}"
    existing_rows = [item for item in existing if item.code != NO_LABEL_CODE]
    codes = {item.code for item in existing_rows}
    leaves = [
        {"geometry": item.geometry}
        for item in existing_rows
        if not item.is_container
    ]
    used_labels = {
        item.label
        for item in existing_rows
        if item.label and not item.is_container
    }
    out: list[AoiDefinitionIn] = []
    if root_code not in codes:
        out.append(
            AoiDefinitionIn(
                code=root_code,
                name=f"Slide {slide_number}",
                parent_id=None,
                geometry={"xMin": 0.0, "yMin": 0.0, "xMax": 1.0, "yMax": 1.0},
                is_container=True,
                kind="system",
                is_active=True,
            )
        )
        codes.add(root_code)
    for candidate in candidates:
        if slide_aoi.overlaps_existing(candidate, leaves):
            continue
        kind = str(candidate.get("kind") or "custom")
        code = slide_aoi.next_code(codes, slide_number, kind)
        codes.add(code)
        label = _next_slide_label(used_labels)
        used_labels.add(label)
        out.append(
            AoiDefinitionIn(
                code=code,
                name=str(candidate.get("name") or "Vùng"),
                label=label,
                parent_id=root_code,
                geometry={
                    "xMin": float(candidate["xMin"]),
                    "yMin": float(candidate["yMin"]),
                    "xMax": float(candidate["xMax"]),
                    "yMax": float(candidate["yMax"]),
                },
                is_container=False,
                kind=kind,
                is_active=True,
            )
        )
    return out


async def _load_candidates(db: AsyncSession, slide) -> list[dict]:
    if slide.aoi_suggestions:
        return list(slide.aoi_suggestions)
    # Một số slide cũ chưa có cache; đọc PDF một trang là best-effort.
    _, lesson, _ = await slide_with_course(db, slide.id)
    asset = await db.get(MediaAsset, lesson.pdf_asset_id) if lesson.pdf_asset_id else None
    if asset is None:
        return []
    try:
        data = await asyncio.to_thread(media_storage.get_bytes, asset.object_key)
        return await asyncio.to_thread(
            slide_aoi.extract_page_from_pdf, data, slide.page_number
        )
    except Exception:  # noqa: BLE001
        return []


async def generate_slide_aois(
    db: AsyncSession,
    user: User,
    slide_id: str,
    body: AoiGenerateIn,
) -> AoiCollectionOut:
    slide, _, _ = await require_slide_manage(db, user, slide_id)
    current_rows = await load_aois(db, slide_id=slide_id)
    if (
        current_rows
        and not body.merge
        and not body.replace_auto
        and not body.reset_all
    ):
        return aoi_collection_out(
            scope="slide",
            slide_id=slide_id,
            ui_schema=None,
            definitions=current_rows,
        )

    current = (
        []
        if body.reset_all
        else [definition_to_input(item) for item in current_rows]
    )
    if body.replace_auto:
        current = [
            item
            for item in current
            if not (
                item.kind in AUTO_KINDS
                and item.code.startswith(f"slide_{slide.position + 1}_")
            )
        ]
    candidates = await _load_candidates(db, slide)
    generated = _build_generated(
        body.slide_number or slide.page_number or slide.position + 1,
        candidates,
        current,
    )
    definitions = await replace_aois(
        db,
        scope="slide",
        slide_id=slide_id,
        ui_schema=None,
        definitions=current + generated,
    )
    return aoi_collection_out(
        scope="slide",
        slide_id=slide_id,
        ui_schema=None,
        definitions=definitions,
    )


async def save_slide_aois(
    db: AsyncSession, user: User, slide_id: str, body
) -> AoiCollectionOut:
    await require_slide_manage(db, user, slide_id)
    definitions = await replace_aois(
        db,
        scope="slide",
        slide_id=slide_id,
        ui_schema=None,
        definitions=body.definitions,
    )
    return aoi_collection_out(
        scope="slide",
        slide_id=slide_id,
        ui_schema=None,
        definitions=definitions,
    )


async def generate_ui_aois(
    db: AsyncSession, user: User, ui_schema: str, body: AoiUiGenerateIn
) -> AoiCollectionOut:
    await require_ui_manage(db, user)
    current_rows = await load_aois(db, ui_schema=ui_schema)
    if current_rows and not body.merge:
        return aoi_collection_out(
            scope="ui",
            slide_id=None,
            ui_schema=ui_schema,
            definitions=current_rows,
        )
    current = [definition_to_input(item) for item in current_rows]
    codes = {item.code for item in current}
    generated = [
        AoiDefinitionIn(
            code=component.code,
            name=component.name,
            parent_id=None,
            geometry={"selector": f"[data-aoi='{component.code}']"},
            is_container=False,
            kind="ui",
            is_active=True,
        )
        for component in body.components
        if component.code not in codes
    ]
    definitions = await replace_aois(
        db,
        scope="ui",
        slide_id=None,
        ui_schema=ui_schema,
        definitions=current + generated,
    )
    return aoi_collection_out(
        scope="ui",
        slide_id=None,
        ui_schema=ui_schema,
        definitions=definitions,
    )


async def save_ui_aois(
    db: AsyncSession, user: User, ui_schema: str, body
) -> AoiCollectionOut:
    await require_ui_manage(db, user)
    definitions_rows = await replace_aois(
        db,
        scope="ui",
        slide_id=None,
        ui_schema=ui_schema,
        definitions=body.definitions,
    )
    return aoi_collection_out(
        scope="ui",
        slide_id=None,
        ui_schema=ui_schema,
        definitions=definitions_rows,
    )
