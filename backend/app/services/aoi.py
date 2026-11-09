"""AOI sets: draft/published, slide/UI scope, generated suggestions.

Bộ vùng slide gắn với từng `SlideVersion`; bộ vùng giao diện dùng chung theo
`ui_schema_version`. Mỗi bộ luôn có định nghĩa hệ thống `no_label` để phân loại
các mẫu gaze không rơi vào vùng lá nào.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import can_access_course, can_manage_course
from app.models.aoi import AoiDefinition, AoiSet
from app.models.auth import User
from app.models.course import (
    Course,
    Lesson,
    LessonVersionSlide,
    Slide,
    SlideVersion,
)
from app.models.media import MediaAsset
from app.schemas.aoi import (
    AoiDefinitionIn,
    AoiDefinitionOut,
    AoiSetGenerateIn,
    AoiSetOut,
    AoiSetSaveIn,
    AoiUiComponentIn,
    AoiUiGenerateIn,
)
from app.services import media_storage, slide_aoi

NO_LABEL_CODE = "no_label"
NO_LABEL_NAME = "Chưa đánh dấu"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _not_found(message: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=message)


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail=message)


def _conflict(message: str) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        detail={"code": "aoi_revision_conflict", "message": message},
    )


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


async def _slide_version_course(
    db: AsyncSession, slide_version_id: str
) -> tuple[SlideVersion, Slide, Lesson, Course]:
    slide_version = await db.get(SlideVersion, slide_version_id)
    if slide_version is None:
        raise _not_found("Không tìm thấy phiên bản slide")
    slide = await db.get(Slide, slide_version.slide_id)
    lesson = await db.get(Lesson, slide.lesson_id) if slide else None
    course = await db.get(Course, lesson.course_id) if lesson else None
    if slide is None or lesson is None or course is None:
        raise _not_found("Không tìm thấy khóa học của slide")
    return slide_version, slide, lesson, course


async def _require_slide_access(
    db: AsyncSession, user: User, slide_version_id: str
) -> None:
    _, _, _, course = await _slide_version_course(db, slide_version_id)
    if not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")


async def _require_slide_manage(
    db: AsyncSession, user: User, slide_version_id: str
) -> None:
    _, _, _, course = await _slide_version_course(db, slide_version_id)
    if not await can_manage_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")


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


async def published_aoi_set(
    db: AsyncSession,
    *,
    slide_version_id: str | None = None,
    ui_schema_version: str | None = None,
) -> AoiSet | None:
    stmt = select(AoiSet).where(AoiSet.state == "published")
    if slide_version_id:
        stmt = stmt.where(AoiSet.slide_version_id == slide_version_id)
    elif ui_schema_version:
        stmt = stmt.where(AoiSet.ui_schema_version == ui_schema_version)
    else:
        return None
    return (await db.execute(stmt)).scalar_one_or_none()


async def _latest_set_for_slide(
    db: AsyncSession, slide_version_id: str
) -> AoiSet | None:
    rows = list(
        (
            await db.execute(
                select(AoiSet)
                .where(
                    AoiSet.scope == "slide",
                    AoiSet.slide_version_id == slide_version_id,
                )
                .order_by(AoiSet.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    draft = next((row for row in rows if row.state == "draft"), None)
    published = next((row for row in rows if row.state == "published"), None)
    return draft or published


async def _latest_set_for_ui(
    db: AsyncSession, ui_schema_version: str
) -> AoiSet | None:
    rows = list(
        (
            await db.execute(
                select(AoiSet)
                .where(
                    AoiSet.scope == "ui",
                    AoiSet.ui_schema_version == ui_schema_version,
                )
                .order_by(AoiSet.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    draft = next((row for row in rows if row.state == "draft"), None)
    published = next((row for row in rows if row.state == "published"), None)
    return draft or published


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
