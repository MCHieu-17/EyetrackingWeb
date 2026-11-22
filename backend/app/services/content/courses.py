"""Teacher course list, creation, metadata and deletion."""

from __future__ import annotations

import asyncio

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.helpers import escape_like
from app.models.auth import User
from app.models.course import Course, CourseTeacher, Lesson
from app.models.media import MediaAsset
from app.models.profile import TeacherProfile
from app.schemas.course import TeacherCourseOut
from app.services import media_storage
from app.services.content.common import _now, logger


async def list_teacher_courses(
    db: AsyncSession,
    user: User,
    *,
    status_filter: str | None = None,
    q: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[TeacherCourseOut]:
    # Đếm bài theo course qua module.
    from app.models.course import CourseModule

    course_lesson_counts = (
        select(
            CourseModule.course_id,
            func.count(Lesson.id).label("lesson_count"),
        )
        .join(Lesson, Lesson.module_id == CourseModule.id)
        .group_by(CourseModule.course_id)
        .subquery()
    )
    stmt = (
        select(
            Course,
            func.coalesce(course_lesson_counts.c.lesson_count, 0).label(
                "lesson_count"
            ),
        )
        .outerjoin(
            course_lesson_counts,
            course_lesson_counts.c.course_id == Course.id,
        )
    )
    if user.role != "admin":
        assigned = select(CourseTeacher.course_id).where(
            CourseTeacher.teacher_id == user.id
        )
        stmt = stmt.where((Course.owner_id == user.id) | Course.id.in_(assigned))
    if q:
        stmt = stmt.where(Course.title.ilike(f"%{escape_like(q)}%", escape="\\"))
    if status_filter in {"archived", "published", "draft"}:
        stmt = stmt.where(Course.status == status_filter)
    elif status_filter:
        return []
    rows = (
        await db.execute(
            stmt.order_by(Course.updated_at.desc()).limit(limit).offset(offset)
        )
    ).all()
    if not rows:
        return []

    from app.services import course_stats

    course_ids = [row[0].id for row in rows]
    stats = await course_stats.course_rollup_cached(db, course_ids)

    return [
        TeacherCourseOut(
            id=course.id,
            title=course.title,
            description=course.description or "",
            gradient="",
            status=course.status,
            students=stats.get(course.id, {}).get("students", 0),
            attention=stats.get(course.id, {}).get("attention"),
            sessions=stats.get(course.id, {}).get("sessions", 0),
            updated_at=course.updated_at,
            is_owner=user.role == "admin" or course.owner_id == user.id,
            lesson_count=int(lesson_count),
            show_gaze_dot=course.show_gaze_dot,
            require_calibration=course.require_calibration,
        )
        for course, lesson_count in rows
    ]


async def create_course(
    db: AsyncSession,
    user: User,
    *,
    title: str,
    description: str | None,
    show_gaze_dot: bool,
    require_calibration: bool,
) -> Course:
    teacher = await db.get(TeacherProfile, user.id)
    if teacher is None:
        if user.role != "admin":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Tài khoản không phải giáo viên",
            )
        teacher = TeacherProfile(
            user_id=user.id,
            teacher_code=f"ADM{user.id[:8].upper()}",
            department="Quản trị hệ thống",
        )
        db.add(teacher)
        await db.flush()

    course = Course(
        owner_id=user.id,
        created_by=user.id,
        title=title,
        description=description,
        status="draft",
        show_gaze_dot=show_gaze_dot,
        require_calibration=require_calibration,
    )
    db.add(course)
    await db.flush()
    return course


async def update_course_metadata(
    db: AsyncSession,
    course: Course,
    user: User,
    *,
    title: str | None = None,
    description: str | None = None,
    show_gaze_dot: bool | None = None,
    require_calibration: bool | None = None,
    status: str | None = None,
) -> Course:
    if title is not None:
        course.title = title
    if description is not None:
        course.description = description
    if show_gaze_dot is not None:
        course.show_gaze_dot = show_gaze_dot
    if require_calibration is not None:
        course.require_calibration = require_calibration
    if status in {"draft", "published", "archived"}:
        course.status = status
        if status == "published" and course.published_at is None:
            course.published_at = _now()
    course.updated_at = _now()
    await db.flush()
    return course


async def delete_course(db: AsyncSession, course: Course) -> None:
    """Xóa khóa học và cascade toàn bộ nội dung/dữ liệu học tập.

    PostgreSQL cascade xử lý DB. File vật lý được lấy key trước rồi dọn sau
    khi transaction commit thành công.
    """
    await db.execute(select(Course.id).where(Course.id == course.id).with_for_update())
    asset_rows = (
        await db.execute(
            select(MediaAsset.object_key, MediaAsset.storage_backend).where(
                MediaAsset.course_id == course.id
            )
        )
    ).all()

    try:
        await db.delete(course)
        await db.flush()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Không thể xóa khóa học vì còn dữ liệu liên quan",
        ) from exc

    r2_keys = [key for key, backend in asset_rows if backend == "r2"]
    local_keys = [key for key, backend in asset_rows if backend == "local"]
    try:
        if r2_keys:
            await asyncio.to_thread(media_storage.delete_keys, r2_keys, "r2")
        if local_keys:
            await asyncio.to_thread(media_storage.delete_keys, local_keys, "local")
    except media_storage.StorageError as exc:
        logger.warning("Không xóa được một số tệp của khóa %s: %s", course.id, exc)

    prefix = f"instances/{settings.app_instance_id}/courses/{course.id}/"
    try:
        await asyncio.to_thread(media_storage.delete_prefix, prefix)
    except media_storage.StorageError:
        logger.warning("Không dọn được prefix media %s", prefix, exc_info=True)
