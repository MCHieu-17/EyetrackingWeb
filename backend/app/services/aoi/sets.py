"""AOI set listing, revisioning, and save/publish flows."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aoi import AoiDefinition, AoiSet
from app.models.auth import User
from app.schemas.aoi import AoiSetOut, AoiSetSaveIn

from .access import (
    _latest_set_for_slide,
    _latest_set_for_ui,
    _require_slide_access,
    _require_slide_manage,
)
from .common import NO_LABEL_CODE, _bad_request, _conflict, _now
from .definitions import _definitions, _replace_definitions, _set_out


async def list_aoi_sets(
    db: AsyncSession,
    user: User,
    *,
    scope: str | None = None,
    slide_version_id: str | None = None,
    ui_schema_version: str | None = None,
    state: str | None = None,
) -> list[AoiSetOut]:
    stmt = select(AoiSet).order_by(AoiSet.created_at.desc())
    if scope:
        stmt = stmt.where(AoiSet.scope == scope)
    if slide_version_id:
        stmt = stmt.where(AoiSet.slide_version_id == slide_version_id)
    if ui_schema_version:
        stmt = stmt.where(AoiSet.ui_schema_version == ui_schema_version)
    if state:
        stmt = stmt.where(AoiSet.state == state)
    rows = list((await db.execute(stmt)).scalars().all())
    out: list[AoiSetOut] = []
    for row in rows:
        if row.scope == "slide" and row.slide_version_id:
            try:
                await _require_slide_access(db, user, row.slide_version_id)
            except HTTPException:
                continue
        out.append(_set_out(row, await _definitions(db, row.id)))
    return out


async def _next_revision(
    db: AsyncSession,
    *,
    scope: str,
    slide_version_id: str | None,
    ui_schema_version: str | None,
) -> int:
    stmt = select(func.coalesce(func.max(AoiSet.revision), 0)).where(
        AoiSet.scope == scope
    )
    if scope == "slide":
        stmt = stmt.where(AoiSet.slide_version_id == slide_version_id)
    else:
        stmt = stmt.where(AoiSet.ui_schema_version == ui_schema_version)
    return int((await db.execute(stmt)).scalar_one()) + 1


async def _publish_draft(db: AsyncSession, row: AoiSet) -> AoiSetOut:
    definitions = await _definitions(db, row.id)
    real = [item for item in definitions if item.code != NO_LABEL_CODE]
    if not real:
        raise _bad_request("Bộ vùng chưa có định nghĩa nào")

    target = (
        AoiSet.slide_version_id == row.slide_version_id
        if row.scope == "slide"
        else AoiSet.ui_schema_version == row.ui_schema_version
    )
    previous = (
        await db.execute(
            select(AoiSet).where(
                AoiSet.scope == row.scope,
                target,
                AoiSet.state == "published",
                AoiSet.id != row.id,
            )
        )
    ).scalars().all()
    for item in previous:
        item.state = "archived"
    await db.flush()

    row.state = "published"
    row.published_at = _now()
    await db.commit()
    await db.refresh(row)
    return _set_out(row, await _definitions(db, row.id))


async def _clone_to_draft(
    db: AsyncSession, source: AoiSet, user: User
) -> AoiSet:
    revision = await _next_revision(
        db,
        scope=source.scope,
        slide_version_id=source.slide_version_id,
        ui_schema_version=source.ui_schema_version,
    )
    draft = AoiSet(
        scope=source.scope,
        slide_version_id=source.slide_version_id,
        ui_schema_version=source.ui_schema_version,
        revision=revision,
        state="draft",
        created_by=user.id,
    )
    db.add(draft)
    await db.flush()

    source_definitions = await _definitions(db, source.id)
    by_id: dict[str, AoiDefinition] = {}
    for item in source_definitions:
        row = AoiDefinition(
            aoi_set_id=draft.id,
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
        by_id[item.id] = row
    for item in source_definitions:
        if item.parent_id and item.parent_id in by_id:
            by_id[item.id].parent_id = by_id[item.parent_id].id
    await db.flush()
    return draft


async def save_slide_aoi_set(
    db: AsyncSession,
    user: User,
    slide_version_id: str,
    body: AoiSetSaveIn,
) -> AoiSetOut:
    await _require_slide_manage(db, user, slide_version_id)
    row = await _latest_set_for_slide(db, slide_version_id)
    if row is None:
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
    else:
        if body.expected_revision is not None and row.revision != body.expected_revision:
            raise _conflict("Bộ vùng đã thay đổi ở nơi khác. Hãy tải lại.")
        if row.state == "published":
            row = await _clone_to_draft(db, row, user)
    await _replace_definitions(db, row.id, body.definitions, "slide")
    return await _publish_draft(db, row)


async def save_ui_aoi_set(
    db: AsyncSession,
    user: User,
    ui_schema_version: str,
    body: AoiSetSaveIn,
) -> AoiSetOut:
    row = await _latest_set_for_ui(db, ui_schema_version)
    if row is None:
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
    else:
        if body.expected_revision is not None and row.revision != body.expected_revision:
            raise _conflict("Bộ vùng đã thay đổi ở nơi khác. Hãy tải lại.")
        if row.state == "published":
            row = await _clone_to_draft(db, row, user)
    await _replace_definitions(db, row.id, body.definitions, "ui")
    return await _publish_draft(db, row)
