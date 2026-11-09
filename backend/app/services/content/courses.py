"""Teacher course list, creation, metadata and deletion."""

from __future__ import annotations

import asyncio

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import settings
from app.core.helpers import escape_like
from app.models.auth import User
from app.models.chat import ChatSession
from app.models.course import (
    Course,
    CourseVersion,
    CourseVersionItem,
    Enrollment,
    Lesson,
    LessonVersion,
    LessonVersionSlide,
    Slide,
    SlideVersion,
)
from app.models.media import MediaAsset, SlideImportJob
from app.models.profile import TeacherProfile
from app.schemas.course import TeacherCourseOut
from app.services import media_storage
from app.services.content.common import (
    _now,
    bump_generation,
    get_draft_version,
    logger,
)


async def list_teacher_courses(
    db: AsyncSession,
    user: User,
    *,
    status_filter: str | None = None,
    q: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[TeacherCourseOut]:
    from app.models.course import CourseTeacher

    published = aliased(CourseVersion)
    draft = aliased(CourseVersion)
    item_counts = (
        select(
            CourseVersionItem.course_version_id,
            func.count(CourseVersionItem.id).label("item_count"),
        )
        .group_by(CourseVersionItem.course_version_id)
        .subquery()
    )
    version_id = func.coalesce(published.id, draft.id)
    stmt = (
        select(
            Course.id,
            Course.owner_id,
            Course.updated_at,
            Course.archived_at,
            Course.show_gaze_dot,
            Course.require_calibration,
            published.id.label("published_id"),
            published.title.label("published_title"),
            published.description.label("published_description"),
            draft.id.label("draft_id"),
            draft.title.label("draft_title"),
            draft.description.label("draft_description"),
            func.coalesce(item_counts.c.item_count, 0).label("item_count"),
        )
        .outerjoin(published, published.id == Course.published_version_id)
        .outerjoin(
            draft,
            and_(draft.course_id == Course.id, draft.state == "draft"),
        )
        .outerjoin(item_counts, item_counts.c.course_version_id == version_id)
    )
    if "admin" not in user.role_codes:
        assigned = select(CourseTeacher.course_id).where(
            CourseTeacher.teacher_id == user.id
        )
        stmt = stmt.where(
            (Course.owner_id == user.id) | Course.id.in_(assigned)
        )
    if q:
        stmt = stmt.where(
            Course.id.in_(
                select(CourseVersion.course_id).where(
                    CourseVersion.title.ilike(
                        f"%{escape_like(q)}%", escape="\\"
                    )
                )
            )
        )
    if status_filter == "archived":
        stmt = stmt.where(Course.archived_at.is_not(None))
    elif status_filter == "published":
        stmt = stmt.where(
            Course.archived_at.is_(None), published.id.is_not(None)
        )
    elif status_filter == "draft":
        stmt = stmt.where(
            Course.archived_at.is_(None), published.id.is_(None)
        )
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

    course_ids = [row.id for row in rows]
    enroll_counts = await course_stats.enrollment_counts(db, course_ids)
    attention = await course_stats.attention_avg_by_course(db, course_ids)
    sessions = await course_stats.session_counts_by_course(db, course_ids)

    out: list[TeacherCourseOut] = []
    for row in rows:
        if row.published_id is not None:
            title = row.published_title
            description = row.published_description
            status_value = (
                "archived" if row.archived_at is not None else "published"
            )
        elif row.draft_id is not None:
            title = row.draft_title
            description = row.draft_description
            status_value = "archived" if row.archived_at is not None else "draft"
        else:
            continue
        out.append(
            TeacherCourseOut(
                id=row.id,
                title=title,
                description=description or "",
                gradient="",
                status=status_value,
                students=enroll_counts.get(row.id, 0),
                attention=attention.get(row.id),
                sessions=sessions.get(row.id, 0),
                updated_at=row.updated_at,
                is_owner="admin" in user.role_codes or row.owner_id == user.id,
                lesson_count=int(row.item_count),
                show_gaze_dot=row.show_gaze_dot,
                require_calibration=row.require_calibration,
            )
        )
    return out


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
        if "admin" not in user.role_codes:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Tài khoản không phải giáo viên"
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
        show_gaze_dot=show_gaze_dot,
        require_calibration=require_calibration,
    )
    db.add(course)
    await db.flush()
    db.add(
        CourseVersion(
            course_id=course.id,
            version_no=1,
            state="draft",
            generation=1,
            title=title,
            description=description,
            created_by=user.id,
        )
    )
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
    archived: bool | None = None,
) -> CourseVersion:
    draft = await get_draft_version(db, course, user)
    assert draft is not None
    if title is not None:
        draft.title = title
    if description is not None:
        draft.description = description
    if show_gaze_dot is not None:
        course.show_gaze_dot = show_gaze_dot
    if require_calibration is not None:
        course.require_calibration = require_calibration
    if archived is not None:
        course.archived_at = _now() if archived else None
    bump_generation(draft)
    await db.flush()
    return draft


async def delete_course(db: AsyncSession, course: Course) -> None:
    """Xóa vĩnh viễn khóa học cùng toàn bộ nội dung, dữ liệu học tập và tệp.

    Thứ tự xóa được chọn để không vi phạm các FK RESTRICT:
    - enrollments kéo theo learning_sessions/quiz_attempts và toàn bộ gaze/AOI runtime;
    - course_versions kéo theo modules/items;
    - lesson_version_slides/slide_versions/slides/lesson_versions trước lessons;
    - media_assets sau cùng trước courses.
    """
    await db.execute(select(Course.id).where(Course.id == course.id).with_for_update())
    # Cho phép các trigger bất biến bỏ qua DELETE trong đúng transaction này.
    await db.execute(text("SET LOCAL app.allow_course_delete = 'on'"))

    asset_rows = (
        await db.execute(
            select(MediaAsset.object_key, MediaAsset.storage_backend).where(
                MediaAsset.course_id == course.id
            )
        )
    ).all()
    job_keys = list(
        (
            await db.execute(
                select(SlideImportJob.source_object_key).where(
                    SlideImportJob.course_id == course.id
                )
            )
        )
        .scalars()
        .all()
    )

    lesson_ids = select(Lesson.id).where(Lesson.course_id == course.id)
    lesson_version_ids = select(LessonVersion.id).where(
        LessonVersion.lesson_id.in_(lesson_ids)
    )
    slide_ids = select(Slide.id).where(Slide.lesson_id.in_(lesson_ids))
    slide_version_ids = select(SlideVersion.id).where(
        SlideVersion.slide_id.in_(slide_ids)
    )

    try:
        await db.execute(
            delete(Enrollment)
            .where(Enrollment.course_id == course.id)
            .execution_options(synchronize_session=False)
        )
        await db.execute(
            delete(ChatSession)
            .where(ChatSession.course_id == course.id)
            .execution_options(synchronize_session=False)
        )
        await db.execute(
            delete(CourseVersion)
            .where(CourseVersion.course_id == course.id)
            .execution_options(synchronize_session=False)
        )
        await db.execute(
            delete(LessonVersionSlide)
            .where(LessonVersionSlide.lesson_version_id.in_(lesson_version_ids))
            .execution_options(synchronize_session=False)
        )
        await db.execute(
            delete(SlideVersion)
            .where(SlideVersion.id.in_(slide_version_ids))
            .execution_options(synchronize_session=False)
        )
        await db.execute(
            delete(Slide)
            .where(Slide.id.in_(slide_ids))
            .execution_options(synchronize_session=False)
        )
        await db.execute(
            delete(LessonVersion)
            .where(LessonVersion.id.in_(lesson_version_ids))
            .execution_options(synchronize_session=False)
        )
        await db.execute(
            delete(SlideImportJob)
            .where(SlideImportJob.course_id == course.id)
            .execution_options(synchronize_session=False)
        )
        await db.execute(
            delete(Lesson)
            .where(Lesson.course_id == course.id)
            .execution_options(synchronize_session=False)
        )
        # Trigger yêu cầu asset phải ở trạng thái deleted trước khi xóa.
        await db.execute(
            update(MediaAsset)
            .where(MediaAsset.course_id == course.id)
            .values(state="deleted")
            .execution_options(synchronize_session=False)
        )
        await db.execute(
            delete(MediaAsset)
            .where(MediaAsset.course_id == course.id)
            .execution_options(synchronize_session=False)
        )
        await db.execute(
            delete(Course)
            .where(Course.id == course.id)
            .execution_options(synchronize_session=False)
        )
        await db.flush()
    except DBAPIError as exc:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Không thể xóa khóa học vì còn dữ liệu liên quan",
        ) from exc

    r2_keys = [key for key, backend in asset_rows if backend == "r2"]
    local_keys = [key for key, backend in asset_rows if backend == "local"]
    if settings.r2_enabled:
        r2_keys.extend(job_keys)
    else:
        local_keys.extend(job_keys)

    try:
        if r2_keys:
            await asyncio.to_thread(media_storage.delete_keys, r2_keys, "r2")
        if local_keys:
            await asyncio.to_thread(media_storage.delete_keys, local_keys, "local")
    except media_storage.StorageError as exc:
        await db.rollback()
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"Không xóa được tệp của khóa học: {exc}",
        ) from exc

    prefix = f"instances/{settings.app_instance_id}/courses/{course.id}/"
    try:
        await asyncio.to_thread(media_storage.delete_prefix, prefix)
    except media_storage.StorageError:
        logger.warning("Không dọn được prefix media %s", prefix, exc_info=True)
