from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import can_access_course, get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.auth import User
from app.models.course import (
    Course,
    CourseVersion,
    CourseVersionItem,
    Enrollment,
    LessonVersionSlide,
    SlideVersion,
)
from app.models.media import MediaAsset
from app.services import media_storage

router = APIRouter(tags=["media"])


def _ensure_media_in_root(path: Path) -> Path:
    try:
        path.resolve().relative_to(settings.media_path.resolve())
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy file")
    return path


async def _asset_published(db: AsyncSession, asset_id: str) -> bool:
    row = (
        await db.execute(
            select(SlideVersion.id)
            .join(
                LessonVersionSlide,
                LessonVersionSlide.slide_version_id == SlideVersion.id,
            )
            .join(
                CourseVersionItem,
                CourseVersionItem.lesson_version_id
                == LessonVersionSlide.lesson_version_id,
            )
            .join(
                CourseVersion,
                CourseVersion.id == CourseVersionItem.course_version_id,
            )
            .join(Course, Course.published_version_id == CourseVersion.id)
            .where(
                SlideVersion.image_asset_id == asset_id,
                CourseVersion.state == "published",
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return row is not None


@router.get("/media/assets/{asset_id}")
async def get_asset(
    asset_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset = await db.get(MediaAsset, asset_id)
    if asset is None or asset.state != "ready":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy file")
    course = await db.get(Course, asset.course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")

    allowed = await can_access_course(db, course, user)
    if not allowed:
        enrolled = (
            await db.execute(
                select(Enrollment.id).where(
                    Enrollment.course_id == course.id,
                    Enrollment.student_id == user.id,
                    Enrollment.status != "dropped",
                )
            )
        ).scalar_one_or_none()
        allowed = enrolled is not None and await _asset_published(db, asset.id)
    if not allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")

    if asset.storage_backend == "r2" and settings.r2_enabled:
        return RedirectResponse(
            media_storage.asset_url(asset.id, asset.object_key, asset.storage_backend)
        )

    file_path = _ensure_media_in_root(settings.media_path / asset.object_key)
    if not file_path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy file")
    return FileResponse(str(file_path), media_type=asset.mime_type)
