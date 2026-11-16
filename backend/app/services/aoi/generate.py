"""AOI generation for UI components (slide AOIs are teacher-drawn)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.schemas.aoi import AoiCollectionOut, AoiDefinitionIn, AoiUiGenerateIn

from .access import require_slide_manage, require_ui_manage
from .definitions import (
    aoi_collection_out,
    definition_to_input,
    load_aois,
    replace_aois,
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
