"""Access policy dùng chung, không phụ thuộc lớp HTTP."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.calibration import GazeCalibration
from app.models.course import Course, CourseTeacher


def validate_uuid(value: str, detail: str = "Không tìm thấy bài học") -> None:
    try:
        uuid.UUID(value)
    except ValueError:
        from fastapi import HTTPException, status

        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=detail)


async def can_manage_course(
    db: AsyncSession, course: Course, user: User
) -> bool:
    """True nếu user là admin hoặc chủ khóa học."""
    del db
    if "admin" in user.role_codes:
        return True
    return course.owner_id == user.id


async def can_access_course(
    db: AsyncSession, course: Course, user: User
) -> bool:
    """True nếu user quản lý khóa hoặc là giáo viên được phân công."""
    if await can_manage_course(db, course, user):
        return True
    if "teacher" not in user.role_codes:
        return False
    stmt = select(CourseTeacher.course_id).where(
        CourseTeacher.course_id == course.id,
        CourseTeacher.teacher_id == user.id,
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None


async def current_calibration(
    db: AsyncSession, user_id: str, fingerprint: str
) -> GazeCalibration | None:
    """Calibration hiện hành = row mới nhất của user trên thiết bị."""
    return (
        await db.execute(
            select(GazeCalibration)
            .where(
                GazeCalibration.user_id == user_id,
                GazeCalibration.device_fingerprint == fingerprint,
            )
            .order_by(GazeCalibration.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
