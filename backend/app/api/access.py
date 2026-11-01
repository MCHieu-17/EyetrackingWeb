"""Helper truy cập dùng chung cho các route.

Gom logic lặp lại giữa courses/modules/lessons/analytics/media/calibration.
Nguyên tắc: giữ nguyên status code + error message như trước khi gom.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import can_access_course, can_manage_course
from app.models.auth import User
from app.models.calibration import CalibrationParam, Device
from app.models.course import Course, Lesson, Module


def validate_uuid(value: str, detail: str = "Không tìm thấy bài học") -> None:
    try:
        uuid.UUID(value)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=detail)


async def get_course_or_404(db: AsyncSession, course_id: str) -> Course:
    course = await db.get(Course, course_id)
    if course is None or course.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    return course


async def get_owned_course(db: AsyncSession, course_id: str, user: User) -> Course:
    """Khóa học mà user quản lý được (admin hoặc chủ khóa)."""
    course = await get_course_or_404(db, course_id)
    if not await can_manage_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    return course


async def get_viewable_course(db: AsyncSession, course_id: str, user: User) -> Course:
    """Khóa học mà user xem được (admin / chủ khóa / GV được phân công)."""
    course = await get_course_or_404(db, course_id)
    if not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    return course


async def get_module_owned(db: AsyncSession, module_id: str, user: User) -> Module:
    module = await db.get(Module, module_id)
    if module is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chương")
    await get_owned_course(db, module.course_id, user)
    return module


async def get_lesson_or_404(db: AsyncSession, lesson_id: str) -> Lesson:
    validate_uuid(lesson_id)
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài học")
    return lesson


async def course_of_lesson(db: AsyncSession, lesson: Lesson) -> Course | None:
    module = await db.get(Module, lesson.module_id)
    return await db.get(Course, module.course_id) if module else None


async def get_lesson_viewable(db: AsyncSession, lesson_id: str, user: User) -> Lesson:
    """Bài học mà user xem được (admin / chủ khóa / GV được phân công)."""
    lesson = await get_lesson_or_404(db, lesson_id)
    course = await course_of_lesson(db, lesson)
    if course is None or not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    return lesson


def escape_like(q: str) -> str:
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def course_lesson_counts(
    db: AsyncSession, course_ids: list[str]
) -> dict[str, int]:
    """Số bài giảng (item bất kỳ) của mỗi khóa."""
    counts: dict[str, int] = {}
    if not course_ids:
        return counts
    rows = await db.execute(
        select(Module.course_id, func.count(Lesson.id))
        .join(Lesson, Lesson.module_id == Module.id)
        .where(Module.course_id.in_(course_ids))
        .group_by(Module.course_id)
    )
    for course_id, total in rows:
        counts[course_id] = total
    return counts


async def active_calibration_param(
    db: AsyncSession, user_id: str, device_id: str
) -> CalibrationParam | None:
    stmt = select(CalibrationParam).where(
        CalibrationParam.user_id == user_id,
        CalibrationParam.device_id == device_id,
        CalibrationParam.is_active.is_(True),
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def upsert_device(
    db: AsyncSession,
    *,
    user_id: str,
    fingerprint: str,
    screen_width_px: int | None,
    screen_height_px: int | None,
) -> Device:
    stmt = (
        select(Device)
        .where(Device.user_id == user_id, Device.device_fingerprint == fingerprint)
        .with_for_update()
    )
    device = (await db.execute(stmt)).scalar_one_or_none()
    if device is None:
        device = Device(
            user_id=user_id,
            device_fingerprint=fingerprint,
            screen_width_px=screen_width_px,
            screen_height_px=screen_height_px,
        )
        db.add(device)
        await db.flush()
    else:
        if screen_width_px:
            device.screen_width_px = screen_width_px
        if screen_height_px:
            device.screen_height_px = screen_height_px
    return device
