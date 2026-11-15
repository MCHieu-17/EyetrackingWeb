"""Đọc AOI hiện hành theo slide hoặc UI schema."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.schemas.aoi import AoiCollectionOut

from .access import require_slide_manage, require_ui_manage
from .definitions import aoi_collection_out, load_aois


async def list_aoi_collections(
    db: AsyncSession,
    user: User,
    *,
    slide_id: str | None = None,
    ui_schema: str | None = None,
) -> list[AoiCollectionOut]:
    if ui_schema:
        await require_ui_manage(db, user)
        rows = await load_aois(db, ui_schema=ui_schema)
        return [
            aoi_collection_out(
                scope="ui",
                slide_id=None,
                ui_schema=ui_schema,
                definitions=rows,
            )
        ]
    if slide_id:
        await require_slide_manage(db, user, slide_id)
        rows = await load_aois(db, slide_id=slide_id)
        return [
            aoi_collection_out(
                scope="slide",
                slide_id=slide_id,
                ui_schema=None,
                definitions=rows,
            )
        ]
    return []
