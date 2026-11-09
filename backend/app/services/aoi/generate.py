"""AOI set generation from slide layout candidates and UI components."""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aoi import AoiDefinition, AoiSet
from app.models.auth import User
from app.models.course import LessonVersionSlide, SlideVersion
from app.models.media import MediaAsset
from app.schemas.aoi import (
    AoiDefinitionIn,
    AoiSetGenerateIn,
    AoiSetOut,
    AoiUiComponentIn,
    AoiUiGenerateIn,
)
from app.services import media_storage, slide_aoi

from .access import (
    _latest_set_for_slide,
    _latest_set_for_ui,
    _require_slide_manage,
    _slide_version_course,
)
from .common import NO_LABEL_CODE
from .definitions import (
    _definition_to_input,
    _definition_to_input_with_codes,
    _definitions,
    _insert_definitions,
    _replace_definitions,
    _set_out,
)
from .sets import _clone_to_draft, _next_revision, _publish_draft


async def _slide_number(db: AsyncSession, slide_version_id: str) -> int | None:
    row = (
        await db.execute(
            select(LessonVersionSlide)
            .where(LessonVersionSlide.slide_version_id == slide_version_id)
            .order_by(LessonVersionSlide.position)
            .limit(1)
        )
    ).scalar_one_or_none()
    return row.position + 1 if row is not None else None


async def _load_slide_candidates(
    db: AsyncSession, slide_version: SlideVersion
) -> list[dict]:
    cached = slide_aoi.candidates_from_metadata(slide_version.render_metadata)
    if cached:
        return cached
    asset = await db.get(MediaAsset, slide_version.source_pdf_asset_id)
    if asset is None:
        return []
    try:
        data = await asyncio.to_thread(media_storage.get_bytes, asset.object_key)
        # `slide_versions` là bất biến sau publish nên không ghi lại cache vào
        # `render_metadata`. Slide cũ sẽ re-extract từ PDF khi giáo viên bấm
        # "Tạo lại gợi ý"; chi phí PyMuPDF cho một trang là không đáng kể.
        return await asyncio.to_thread(
            slide_aoi.extract_page_from_pdf, data, slide_version.source_page
        )
    except Exception:  # noqa: BLE001 - gợi ý lỗi không chặn giáo viên
        return []


def _build_generated_definitions(
    slide_number: int,
    candidates: list[dict],
    existing: list[dict],
    existing_codes: set[str],
) -> list[AoiDefinitionIn]:
    root_code = f"slide_{slide_number}"
    definitions: list[AoiDefinitionIn] = []
    if root_code not in existing_codes:
        definitions.append(
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
        existing_codes.add(root_code)

    for candidate in candidates:
        if slide_aoi.overlaps_existing(candidate, existing):
            continue
        kind = str(candidate.get("kind") or "custom")
        code = slide_aoi.next_code(existing_codes, slide_number, kind)
        existing_codes.add(code)
        definitions.append(
            AoiDefinitionIn(
                code=code,
                name=str(candidate.get("name") or "Vùng"),
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
    return definitions


AUTO_KINDS = {"text", "image", "table"}


def _is_auto_definition(item: AoiDefinition, slide_number: int) -> bool:
    root_code = f"slide_{slide_number}"
    return (
        item.kind in AUTO_KINDS
        and item.code.startswith(f"{root_code}_")
        and item.code != root_code
    )


def _resolve_slide_number(current: list[AoiDefinition], fallback: int) -> int:
    roots = [
        item
        for item in current
        if item.is_container and item.code.startswith("slide_")
    ]
    root = next(
        (
            item
            for item in roots
            if item.code.removeprefix("slide_").isdigit()
        ),
        roots[0] if roots else None,
    )
    if root is None:
        return fallback
    suffix = root.code.removeprefix("slide_")
    return int(suffix) if suffix.isdigit() else fallback


async def generate_slide_aoi_set(
    db: AsyncSession,
    user: User,
    slide_version_id: str,
    body: AoiSetGenerateIn,
) -> AoiSetOut:
    await _require_slide_manage(db, user, slide_version_id)
    slide_version, _, _, _ = await _slide_version_course(db, slide_version_id)
    slide_number = (
        body.slide_number
        or await _slide_number(db, slide_version_id)
        or slide_version.source_page
    )
    existing = await _latest_set_for_slide(db, slide_version_id)
    if (
        existing is not None
        and not body.merge
        and not body.replace_auto
        and not body.reset_all
    ):
        return _set_out(existing, await _definitions(db, existing.id))

    candidates = await _load_slide_candidates(db, slide_version)

    if existing is None:
        row = AoiSet(
            scope="slide",
            slide_version_id=slide_version_id,
            revision=await _next_revision(
                db,
                scope="slide",
                slide_version_id=slide_version_id,
                ui_schema_version=None,
            ),
            state="draft",
            created_by=user.id,
        )
        db.add(row)
        await db.flush()
        definitions = _build_generated_definitions(
            slide_number, candidates, existing=[], existing_codes=set()
        )
        await _insert_definitions(db, row.id, definitions, "slide")
        return await _publish_draft(db, row)

    if existing.state == "published":
        row = await _clone_to_draft(db, existing, user)
    else:
        row = existing

    current = await _definitions(db, row.id)
    slide_number = _resolve_slide_number(current, slide_number)

    if body.replace_auto or body.reset_all:
        root = next(
            (
                item
                for item in current
                if item.is_container and item.code == f"slide_{slide_number}"
            ),
            None,
        )
        if root is None:
            root = next(
                (
                    item
                    for item in current
                    if item.is_container and item.code.startswith("slide_")
                ),
                None,
            )
        root_code = root.code if root is not None else f"slide_{slide_number}"
        suffix = root_code.removeprefix("slide_")
        if suffix.isdigit():
            slide_number = int(suffix)

        removed_ids = {
            item.id
            for item in current
            if item.code != NO_LABEL_CODE
            and item.code != root_code
            and (body.reset_all or _is_auto_definition(item, slide_number))
        }
        kept = [
            item
            for item in current
            if item.id not in removed_ids and item.code != NO_LABEL_CODE
        ]
        for item in kept:
            if item.parent_id in removed_ids:
                item.parent_id = root.id if root is not None else None
        code_by_id = {item.id: item.code for item in kept}
        existing_leaves = [
            {"geometry": item.geometry}
            for item in kept
            if not item.is_container
        ]
        existing_codes = {item.code for item in kept}
        new_definitions = _build_generated_definitions(
            slide_number,
            candidates,
            existing=existing_leaves,
            existing_codes=existing_codes,
        )
        all_definitions = [
            _definition_to_input_with_codes(item, code_by_id) for item in kept
        ] + new_definitions
        await _replace_definitions(db, row.id, all_definitions, "slide")
        return await _publish_draft(db, row)

    existing_codes = {item.code for item in current}
    existing_leaves = [
        {"geometry": item.geometry}
        for item in current
        if not item.is_container and item.code != NO_LABEL_CODE
    ]
    new_definitions = _build_generated_definitions(
        slide_number,
        candidates,
        existing=existing_leaves,
        existing_codes=existing_codes,
    )
    if new_definitions:
        code_by_id = {item.id: item.code for item in current}
        all_definitions = [
            _definition_to_input_with_codes(item, code_by_id)
            for item in current
            if item.code != NO_LABEL_CODE
        ] + new_definitions
        await _replace_definitions(db, row.id, all_definitions, "slide")
    return await _publish_draft(db, row)


def _build_ui_definitions(
    components: list[AoiUiComponentIn],
    existing_codes: set[str],
) -> list[AoiDefinitionIn]:
    definitions: list[AoiDefinitionIn] = []
    for component in components:
        if component.code in existing_codes:
            continue
        existing_codes.add(component.code)
        definitions.append(
            AoiDefinitionIn(
                code=component.code,
                name=component.name,
                parent_id=None,
                geometry={"selector": f"[data-aoi='{component.code}']"},
                is_container=False,
                kind="ui",
                is_active=True,
            )
        )
    return definitions


async def generate_ui_aoi_set(
    db: AsyncSession,
    user: User,
    ui_schema_version: str,
    body: AoiUiGenerateIn,
) -> AoiSetOut:
    existing = await _latest_set_for_ui(db, ui_schema_version)
    if existing is not None and not body.merge:
        return _set_out(existing, await _definitions(db, existing.id))

    if existing is None:
        row = AoiSet(
            scope="ui",
            ui_schema_version=ui_schema_version,
            revision=await _next_revision(
                db,
                scope="ui",
                slide_version_id=None,
                ui_schema_version=ui_schema_version,
            ),
            state="draft",
            created_by=user.id,
        )
        db.add(row)
        await db.flush()
        definitions = _build_ui_definitions(body.components, set())
        await _insert_definitions(db, row.id, definitions, "ui")
        return await _publish_draft(db, row)

    if existing.state == "published":
        row = await _clone_to_draft(db, existing, user)
    else:
        row = existing

    current = await _definitions(db, row.id)
    existing_codes = {item.code for item in current}
    new_definitions = _build_ui_definitions(body.components, existing_codes)
    if new_definitions:
        all_definitions = [
            _definition_to_input(item)
            for item in current
            if item.code != NO_LABEL_CODE
        ] + new_definitions
        await _replace_definitions(db, row.id, all_definitions, "ui")
    return await _publish_draft(db, row)
