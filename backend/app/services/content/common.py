"""Shared helpers for the simplified content service."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course, CourseModule, Lesson
from app.models.media import MediaAsset
from app.services import media_storage

logger = logging.getLogger("app.services.content")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _not_found(message: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=message)


async def get_course_or_404(db: AsyncSession, course_id: str) -> Course:
    course = await db.get(Course, course_id)
    if course is None:
        raise _not_found("Không tìm thấy khóa học")
    return course


async def course_of_module(
    db: AsyncSession, module_id: str
) -> tuple[Course, CourseModule]:
    module = await db.get(CourseModule, module_id)
    if module is None:
        raise _not_found("Không tìm thấy chương")
    course = await db.get(Course, module.course_id)
    if course is None:
        raise _not_found("Không tìm thấy khóa học")
    return course, module


async def course_of_lesson(db: AsyncSession, lesson_id: str) -> tuple[Course, Lesson]:
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise _not_found("Không tìm thấy bài học")
    module = await db.get(CourseModule, lesson.module_id)
    if module is None:
        raise _not_found("Không tìm thấy chương")
    course = await db.get(Course, module.course_id)
    if course is None:
        raise _not_found("Không tìm thấy khóa học")
    return course, lesson


def touch_course(course: Course) -> None:
    course.updated_at = _now()


def touch_lesson(lesson: Lesson) -> None:
    lesson.updated_at = _now()


async def delete_unreferenced_assets(
    db: AsyncSession, asset_ids: Iterable[str | None]
) -> list[tuple[str, str]]:
    """Xóa các `media_assets` không còn lesson nào tham chiếu.

    Trả về danh sách `(object_key, storage_backend)` để route xóa file vật lý
    sau khi transaction commit thành công. Không xóa asset còn được lesson
    khác dùng chung (cùng sha256 trong một khóa học).
    """
    removed: list[tuple[str, str]] = []
    for asset_id in {asset_id for asset_id in asset_ids if asset_id}:
        still_used = (
            await db.execute(
                select(Lesson.id).where(Lesson.pdf_asset_id == asset_id).limit(1)
            )
        ).first()
        if still_used is not None:
            continue
        asset = await db.get(MediaAsset, asset_id)
        if asset is None:
            continue
        removed.append((asset.object_key, asset.storage_backend))
        await db.delete(asset)
    return removed


async def delete_media_objects(keys: Iterable[tuple[str, str]]) -> None:
    """Xóa file vật lý sau commit; lỗi lưu trữ chỉ ghi log, không fail request."""
    for key, backend in keys:
        try:
            await asyncio.to_thread(media_storage.delete_key, key, backend)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Không xóa được media %s (backend=%s)", key, backend, exc_info=True
            )
