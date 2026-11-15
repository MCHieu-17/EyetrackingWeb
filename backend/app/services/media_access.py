"""Chính sách truy cập file media.

Tách khỏi route để media route và các service khác dùng cùng một quy tắc.
Route vẫn chịu trách nhiệm map lỗi sang HTTP.
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.course import Course, CourseModule, Enrollment, Lesson
from app.models.media import MediaAsset
from app.services.access import can_access_course


async def asset_published(db: AsyncSession, asset_id: str) -> bool:
    row = (
        await db.execute(
            select(Lesson.id)
            .join(CourseModule, CourseModule.id == Lesson.module_id)
            .join(Course, Course.id == CourseModule.course_id)
            .where(
                Lesson.pdf_asset_id == asset_id,
                Course.status == "published",
            )
            .limit(1)
        )
    ).first()
    return row is not None


async def get_asset_for_user(
    db: AsyncSession, asset_id: str, user: User
) -> MediaAsset:
    asset = await db.get(MediaAsset, asset_id)
    if asset is None or asset.state != "ready":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy file")
    course = await db.get(Course, asset.course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy file")

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
        allowed = enrolled is not None and await asset_published(db, asset.id)
    if not allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    return asset
