"""Content versioning: draft, copy-on-write, publish, outline.

Phase 2 service. Mọi mutation nội dung đi qua đây để giữ:
  - một draft/course;
  - generation guard;
  - published version bất biến;
  - asset/slide version tái sử dụng.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, raiseload, selectinload

from app.core.config import settings
from app.core.helpers import escape_like
from app.db.session import SessionLocal
from app.models.auth import User
from app.models.chat import ChatSession
from app.models.course import (
    ContentAuditEvent,
    Course,
    CourseVersion,
    CourseVersionItem,
    CourseVersionModule,
    Enrollment,
    Lesson,
    LessonVersion,
    LessonVersionSlide,
    Slide,
    SlideVersion,
)
from app.models.media import MediaAsset, SlideDocument, SlideImportJob
from app.models.profile import TeacherProfile
from app.models.quiz import QuizSpec
from app.schemas.course import (
    CourseOutlineOut,
    LessonItemOut,
    LessonNodeOut,
    ModuleItemOut,
    ModuleNodeOut,
    SlideAdminOut,
    SlideOut,
    StudentRowOut,
    TeacherCourseOut,
)
from app.services import media_storage, slide_aoi, slide_import

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _conflict(code: str, message: str) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT, detail={"code": code, "message": message}
    )


def _not_found(message: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=message)


async def get_course_or_404(db: AsyncSession, course_id: str) -> Course:
    course = await db.get(
        Course,
        course_id,
        options=[
            raiseload(Course.versions),
            raiseload(Course.enrollments),
            raiseload(Course.owner),
            raiseload(Course.creator),
        ],
    )
    if course is None:
        raise _not_found("Không tìm thấy khóa học")
    return course


async def get_published_version(
    db: AsyncSession, course: Course
) -> CourseVersion | None:
    if not course.published_version_id:
        return None
    return await db.get(
        CourseVersion,
        course.published_version_id,
        options=[
            raiseload(CourseVersion.modules),
            raiseload(CourseVersion.items),
        ],
    )


async def get_draft_version(
    db: AsyncSession, course: Course, user: User, *, create: bool = True
) -> CourseVersion | None:
    stmt = (
        select(CourseVersion)
        .options(
            raiseload(CourseVersion.modules),
            raiseload(CourseVersion.items),
        )
        .where(
            CourseVersion.course_id == course.id,
            CourseVersion.state == "draft",
        )
    )
    draft = (await db.execute(stmt)).scalar_one_or_none()
    if draft is not None:
        return draft
    if not create:
        return None

    published = await get_published_version(db, course)
    if published is None:
        draft = CourseVersion(
            course_id=course.id,
            version_no=1,
            state="draft",
            generation=1,
            title="Khóa học mới",
            description=None,
            created_by=user.id,
        )
        db.add(draft)
        await db.flush()
        return draft

    draft = await clone_course_version(db, published, user)
    return draft


async def clone_course_version(
    db: AsyncSession, source: CourseVersion, user: User
) -> CourseVersion:
    max_no = (
        await db.execute(
            select(func.coalesce(func.max(CourseVersion.version_no), 0)).where(
                CourseVersion.course_id == source.course_id
            )
        )
    ).scalar_one()
    draft = CourseVersion(
        course_id=source.course_id,
        version_no=max_no + 1,
        state="draft",
        generation=1,
        title=source.title,
        description=source.description,
        thumbnail_asset_id=source.thumbnail_asset_id,
        created_by=user.id,
    )
    db.add(draft)
    await db.flush()

    source_modules = (
        await db.execute(
            select(CourseVersionModule)
            .where(CourseVersionModule.course_version_id == source.id)
            .order_by(CourseVersionModule.position)
            .options(raiseload(CourseVersionModule.items))
        )
    ).scalars().all()
    module_map: dict[str, CourseVersionModule] = {}
    for module in source_modules:
        cloned = CourseVersionModule(
            course_version_id=draft.id,
            module_key=module.module_key,
            title=module.title,
            position=module.position,
        )
        db.add(cloned)
        await db.flush()
        module_map[module.id] = cloned

    source_items = (
        await db.execute(
            select(CourseVersionItem)
            .where(CourseVersionItem.course_version_id == source.id)
            .order_by(CourseVersionItem.position)
        )
    ).scalars().all()
    for item in source_items:
        db.add(
            CourseVersionItem(
                course_version_id=draft.id,
                module_id=module_map[item.module_id].id,
                lesson_id=item.lesson_id,
                lesson_version_id=item.lesson_version_id,
                position=item.position,
            )
        )
    await db.flush()
    return draft


async def clone_lesson_version(
    db: AsyncSession, source: LessonVersion, user: User
) -> LessonVersion:
    max_no = (
        await db.execute(
            select(func.coalesce(func.max(LessonVersion.version_no), 0)).where(
                LessonVersion.lesson_id == source.lesson_id
            )
        )
    ).scalar_one()
    draft = LessonVersion(
        lesson_id=source.lesson_id,
        version_no=max_no + 1,
        state="draft",
        title=source.title,
        created_by=user.id,
    )
    db.add(draft)
    await db.flush()

    source_slides = (
        await db.execute(
            select(LessonVersionSlide)
            .where(LessonVersionSlide.lesson_version_id == source.id)
            .order_by(LessonVersionSlide.position)
            .options(raiseload(LessonVersionSlide.slide_version))
        )
    ).scalars().all()
    for slide in source_slides:
        db.add(
            LessonVersionSlide(
                lesson_version_id=draft.id,
                slide_id=slide.slide_id,
                slide_version_id=slide.slide_version_id,
                position=slide.position,
                title=slide.title,
            )
        )

    source_quiz = await db.get(QuizSpec, source.id)
    if source_quiz is not None:
        db.add(
            QuizSpec(
                lesson_version_id=draft.id,
                instructions=source_quiz.instructions,
                duration_minutes=source_quiz.duration_minutes,
                due_at=source_quiz.due_at,
                allow_retry=source_quiz.allow_retry,
                allow_chatbot=source_quiz.allow_chatbot,
                questions=source_quiz.questions,
            )
        )
    await db.flush()
    return draft


async def ensure_draft_lesson_version(
    db: AsyncSession, item: CourseVersionItem, user: User
) -> LessonVersion:
    lesson_version = await db.get(
        LessonVersion,
        item.lesson_version_id,
        options=[raiseload(LessonVersion.slides)],
    )
    if lesson_version is None:
        raise _not_found("Không tìm thấy phiên bản bài học")
    if lesson_version.state == "draft":
        return lesson_version
    draft = await clone_lesson_version(db, lesson_version, user)
    item.lesson_version_id = draft.id
    await db.flush()
    return draft


def bump_generation(course_version: CourseVersion) -> None:
    course_version.generation += 1


def check_generation(course_version: CourseVersion, expected: int | None) -> None:
    if expected is not None and expected != course_version.generation:
        raise _conflict(
            "content_changed",
            "Nội dung đã thay đổi ở phiên khác. Hãy tải lại trước khi lưu.",
        )


async def get_draft_item_for_lesson(
    db: AsyncSession, course: Course, lesson_id: str, user: User
) -> tuple[CourseVersion, CourseVersionItem]:
    return await _draft_item(db, course, lesson_id, user)


async def _draft_item(
    db: AsyncSession, course: Course, lesson_id: str, user: User
) -> tuple[CourseVersion, CourseVersionItem]:
    draft = await get_draft_version(db, course, user)
    assert draft is not None
    item = (
        await db.execute(
            select(CourseVersionItem).where(
                CourseVersionItem.course_version_id == draft.id,
                CourseVersionItem.lesson_id == lesson_id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise _not_found("Không tìm thấy bài học trong bản nháp")
    return draft, item


async def course_of_module(
    db: AsyncSession, module_id: str
) -> tuple[Course, CourseVersionModule]:
    module = await db.get(
        CourseVersionModule,
        module_id,
        options=[raiseload(CourseVersionModule.items)],
    )
    if module is None:
        raise _not_found("Không tìm thấy chương")
    version = await db.get(
        CourseVersion,
        module.course_version_id,
        options=[
            raiseload(CourseVersion.modules),
            raiseload(CourseVersion.items),
        ],
    )
    if version is None:
        raise _not_found("Không tìm thấy phiên bản khóa học")
    course = await db.get(
        Course,
        version.course_id,
        options=[
            raiseload(Course.versions),
            raiseload(Course.enrollments),
            raiseload(Course.owner),
            raiseload(Course.creator),
        ],
    )
    if course is None:
        raise _not_found("Không tìm thấy khóa học")
    return course, module


async def _draft_module(
    db: AsyncSession, course: Course, module_id: str, user: User
) -> tuple[CourseVersion, CourseVersionModule]:
    draft = await get_draft_version(db, course, user)
    assert draft is not None
    # delete_module dựa vào cascade delete-orphan nên phải tải items trước.
    module = await db.get(
        CourseVersionModule,
        module_id,
        options=[selectinload(CourseVersionModule.items)],
    )
    if module is None or module.course_version_id != draft.id:
        raise _not_found("Không tìm thấy chương trong bản nháp")
    return draft, module


async def _next_item_position(db: AsyncSession, course_version_id: str) -> int:
    value = (
        await db.execute(
            select(func.coalesce(func.max(CourseVersionItem.position), -1) + 1).where(
                CourseVersionItem.course_version_id == course_version_id
            )
        )
    ).scalar_one()
    return int(value)


async def _next_module_position(db: AsyncSession, course_version_id: str) -> int:
    value = (
        await db.execute(
            select(func.coalesce(func.max(CourseVersionModule.position), -1) + 1).where(
                CourseVersionModule.course_version_id == course_version_id
            )
        )
    ).scalar_one()
    return int(value)


async def _renumber_items(
    db: AsyncSession, course_version_id: str, ordered_ids: list[str]
) -> None:
    items = (
        await db.execute(
            select(CourseVersionItem).where(
                CourseVersionItem.course_version_id == course_version_id
            )
        )
    ).scalars().all()
    by_lesson = {item.lesson_id: item for item in items}
    # position có CHECK >= 0 và UNIQUE (course_version_id, position); dùng
    # offset tạm thời thay vì số âm để tránh vi phạm constraint.
    offset = max((item.position for item in items), default=0) + len(items) + 1
    for index, item in enumerate(items):
        item.position = offset + index
    await db.flush()
    for index, lesson_id in enumerate(ordered_ids):
        by_lesson[lesson_id].position = index
    await db.flush()


# ---------------------------------------------------------------------------
# Course list / create / metadata
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Modules / items / lessons
# ---------------------------------------------------------------------------
async def create_module(
    db: AsyncSession, course: Course, user: User, title: str
) -> CourseVersionModule:
    draft = await get_draft_version(db, course, user)
    assert draft is not None
    module = CourseVersionModule(
        course_version_id=draft.id,
        title=title,
        position=await _next_module_position(db, draft.id),
    )
    db.add(module)
    bump_generation(draft)
    await db.flush()
    return module


async def update_module(
    db: AsyncSession, course: Course, user: User, module_id: str, title: str
) -> CourseVersionModule:
    draft, module = await _draft_module(db, course, module_id, user)
    module.title = title
    bump_generation(draft)
    await db.flush()
    return module


async def delete_module(
    db: AsyncSession, course: Course, user: User, module_id: str
) -> None:
    draft, module = await _draft_module(db, course, module_id, user)
    await db.delete(module)
    bump_generation(draft)
    await db.flush()


async def create_lesson(
    db: AsyncSession, course: Course, user: User, module_id: str, title: str
) -> Lesson:
    draft, module = await _draft_module(db, course, module_id, user)
    lesson = Lesson(course_id=course.id, kind="lesson")
    db.add(lesson)
    await db.flush()
    lesson_version = LessonVersion(
        lesson_id=lesson.id,
        version_no=1,
        state="draft",
        title=title,
        created_by=user.id,
    )
    db.add(lesson_version)
    await db.flush()
    db.add(
        CourseVersionItem(
            course_version_id=draft.id,
            module_id=module.id,
            lesson_id=lesson.id,
            lesson_version_id=lesson_version.id,
            position=await _next_item_position(db, draft.id),
        )
    )
    bump_generation(draft)
    await db.flush()
    return lesson


async def create_quiz_item(
    db: AsyncSession,
    course: Course,
    user: User,
    module_id: str,
    *,
    title: str,
    duration_minutes: int,
    due_at: datetime | None,
) -> Lesson:
    draft, module = await _draft_module(db, course, module_id, user)
    lesson = Lesson(course_id=course.id, kind="quiz")
    db.add(lesson)
    await db.flush()
    lesson_version = LessonVersion(
        lesson_id=lesson.id,
        version_no=1,
        state="draft",
        title=title,
        created_by=user.id,
    )
    db.add(lesson_version)
    await db.flush()
    db.add(
        QuizSpec(
            lesson_version_id=lesson_version.id,
            instructions="",
            duration_minutes=duration_minutes,
            due_at=due_at,
            questions=[],
        )
    )
    db.add(
        CourseVersionItem(
            course_version_id=draft.id,
            module_id=module.id,
            lesson_id=lesson.id,
            lesson_version_id=lesson_version.id,
            position=await _next_item_position(db, draft.id),
        )
    )
    bump_generation(draft)
    await db.flush()
    return lesson


async def update_lesson(
    db: AsyncSession, course: Course, user: User, lesson_id: str, title: str
) -> LessonVersion:
    draft, item = await _draft_item(db, course, lesson_id, user)
    lesson_version = await ensure_draft_lesson_version(db, item, user)
    lesson_version.title = title
    bump_generation(draft)
    await db.flush()
    return lesson_version


async def delete_lesson(
    db: AsyncSession, course: Course, user: User, lesson_id: str
) -> None:
    draft, item = await _draft_item(db, course, lesson_id, user)
    await db.delete(item)
    bump_generation(draft)
    await db.flush()


async def reorder_items(
    db: AsyncSession,
    course: Course,
    user: User,
    module_id: str,
    ordered_lesson_ids: list[str],
) -> None:
    draft, module = await _draft_module(db, course, module_id, user)
    items = (
        await db.execute(
            select(CourseVersionItem)
            .where(CourseVersionItem.course_version_id == draft.id)
            .order_by(CourseVersionItem.position)
        )
    ).scalars().all()
    module_items = [item for item in items if item.module_id == module.id]
    by_lesson = {item.lesson_id: item for item in module_items}
    if set(ordered_lesson_ids) != set(by_lesson):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Danh sách item không khớp cấu trúc chương",
        )
    modules = (
        await db.execute(
            select(CourseVersionModule)
            .where(CourseVersionModule.course_version_id == draft.id)
            .order_by(CourseVersionModule.position)
        )
    ).scalars().all()
    global_order: list[str] = []
    for current in modules:
        if current.id == module.id:
            global_order.extend(ordered_lesson_ids)
        else:
            global_order.extend(
                item.lesson_id for item in items if item.module_id == current.id
            )
    await _renumber_items(db, draft.id, global_order)
    bump_generation(draft)
    await db.flush()


# ---------------------------------------------------------------------------
# Slides / media
# ---------------------------------------------------------------------------
def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def _asset_for_bytes(
    db: AsyncSession,
    *,
    course: Course,
    data: bytes,
    mime_type: str,
    object_key: str,
    kind: str = "normalized",
    metadata: dict | None = None,
) -> MediaAsset:
    digest = _sha256(data)
    existing = (
        await db.execute(
            select(MediaAsset).where(
                MediaAsset.course_id == course.id,
                MediaAsset.sha256 == digest,
                MediaAsset.state == "ready",
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        if metadata:
            existing.metadata_ = {**(existing.metadata_ or {}), **metadata}
        return existing

    await asyncio.to_thread(media_storage.put_bytes, object_key, data, mime_type)
    asset = MediaAsset(
        course_id=course.id,
        storage_backend="r2" if settings.r2_enabled else "local",
        object_key=object_key,
        sha256=digest,
        mime_type=mime_type,
        byte_size=len(data),
        state="ready",
        kind=kind,
        metadata_=metadata or {},
    )
    db.add(asset)
    await db.flush()
    return asset


async def create_slide_import(
    db: AsyncSession,
    course: Course,
    user: User,
    lesson_id: str,
    data: bytes,
    filename: str,
    mime: str | None,
) -> SlideImportJob:
    """Nhận file upload, lưu tạm và tạo job chuyển đổi bất đồng bộ."""
    if len(data) > settings.max_upload_bytes:
        limit = settings.max_upload_bytes // (1024 * 1024)
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"File vượt quá {limit}MB cho phép.",
        )

    try:
        fmt = slide_import.detect_format(filename, mime, data)
        if fmt == "pdf":
            slide_import.validate_pdf(data)
    except slide_import.SlideImportError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    draft, item = await _draft_item(db, course, lesson_id, user)
    lesson_version = await ensure_draft_lesson_version(db, item, user)

    # Upload mới thay thế các job còn chờ của cùng lesson version.
    old_jobs = (
        await db.execute(
            select(SlideImportJob).where(
                SlideImportJob.lesson_version_id == lesson_version.id,
                SlideImportJob.status.in_(("queued", "processing")),
            )
        )
    ).scalars().all()
    queued_staging_keys = [
        old.source_object_key for old in old_jobs if old.status == "queued"
    ]
    for old in old_jobs:
        old.status = "cancelled"
        old.finished_at = _now()

    job_id = str(uuid.uuid4())
    suffix = Path(filename or "").suffix.lower() or f".{fmt}"
    staging_key = (
        f"instances/{settings.app_instance_id}/courses/{course.id}/"
        f"lessons/{lesson_id}/imports/{job_id}/upload{suffix}"
    )
    job = SlideImportJob(
        id=job_id,
        course_id=course.id,
        lesson_id=lesson_id,
        lesson_version_id=lesson_version.id,
        created_by=user.id,
        status="queued",
        source_filename=filename or f"slides{suffix}",
        source_mime=slide_import.mime_for_format(fmt),
        source_size=len(data),
        source_sha256=_sha256(data),
        source_object_key=staging_key,
    )
    db.add(job)
    await db.flush()

    try:
        await asyncio.to_thread(
            media_storage.put_bytes, staging_key, data, job.source_mime
        )
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không lưu được file tạm để xử lý.",
        ) from exc

    for key in queued_staging_keys:
        try:
            await asyncio.to_thread(media_storage.delete_key, key)
        except Exception:  # noqa: BLE001
            logger.warning("Không xoá được staging cũ %s", key)

    bump_generation(draft)
    await db.flush()
    return job


async def get_slide_import_job(
    db: AsyncSession, course: Course, lesson_id: str, job_id: str
) -> SlideImportJob:
    job = await db.get(SlideImportJob, job_id)
    if job is None or job.course_id != course.id or job.lesson_id != lesson_id:
        raise _not_found("Không tìm thấy job tải tài liệu")
    return job


async def process_slide_import(job_id: str) -> None:
    """Worker: convert file staging -> PDF, tạo slide_version cho từng trang."""
    async with SessionLocal() as db:
        job = await db.get(SlideImportJob, job_id)
        if job is None or job.status != "processing":
            return
        source_key = job.source_object_key
        ingest_lesson_version_id: str | None = None

        try:
            data = await asyncio.to_thread(media_storage.get_bytes, source_key)
            fmt = slide_import.detect_format(
                job.source_filename, job.source_mime, data
            )
            pdf_bytes = await asyncio.to_thread(
                slide_import.convert_to_pdf, data, fmt, job.source_filename
            )
            page_count = slide_import.validate_pdf(pdf_bytes)
            try:
                aoi_candidates = await asyncio.to_thread(
                    slide_aoi.extract_document_aois, pdf_bytes
                )
            except Exception:  # noqa: BLE001 - gợi ý lỗi không chặn import
                logger.warning("Không trích xuất được gợi ý vùng AOI", exc_info=True)
                aoi_candidates = {}

            course = await db.get(
                Course,
                job.course_id,
                options=[
                    raiseload(Course.versions),
                    raiseload(Course.enrollments),
                    raiseload(Course.owner),
                    raiseload(Course.creator),
                ],
            )
            user = await db.get(
                User,
                job.created_by,
                options=[raiseload(User.roles)],
            )
            lesson_version = await db.get(
                LessonVersion,
                job.lesson_version_id,
                options=[raiseload(LessonVersion.slides)],
            )
            if course is None or user is None or lesson_version is None:
                raise RuntimeError("Job thiếu course/user/lesson version")

            await db.refresh(job)
            if job.status != "processing":
                return
            if lesson_version.state != "draft":
                raise RuntimeError(
                    "Bản nháp đã được xuất bản trong lúc xử lý; hãy tải lại và thử lại."
                )

            prefix = (
                f"instances/{settings.app_instance_id}/courses/{course.id}/"
                f"lessons/{job.lesson_id}/{uuid.uuid4().hex[:12]}"
            )
            pdf_asset = await _asset_for_bytes(
                db,
                course=course,
                data=pdf_bytes,
                mime_type="application/pdf",
                object_key=f"{prefix}/source.pdf",
                kind="normalized",
                metadata={
                    "page_count": page_count,
                    "source_format": fmt,
                    "converter": "libreoffice",
                },
            )

            # Gỡ membership cũ; slide version/asset cũ vẫn giữ trong lịch sử.
            await db.execute(
                delete(LessonVersionSlide).where(
                    LessonVersionSlide.lesson_version_id == lesson_version.id
                )
            )
            slides = [Slide(lesson_id=job.lesson_id) for _ in range(page_count)]
            db.add_all(slides)
            await db.flush()

            slide_versions = [
                SlideVersion(
                    slide_id=slide.id,
                    revision_no=1,
                    source_pdf_asset_id=pdf_asset.id,
                    source_page=page_no,
                    render_metadata={
                        "converter": "libreoffice",
                        "source_format": fmt,
                        "page_count": page_count,
                        "aoi_layout_version": slide_aoi.AOI_LAYOUT_VERSION,
                        "aoi_candidates": aoi_candidates.get(page_no, []),
                    },
                    created_by=job.created_by,
                )
                for page_no, slide in enumerate(slides, start=1)
            ]
            db.add_all(slide_versions)
            await db.flush()

            db.add_all(
                [
                    LessonVersionSlide(
                        lesson_version_id=lesson_version.id,
                        slide_id=slide.id,
                        slide_version_id=slide_version.id,
                        position=page_no - 1,
                        title=f"Slide {page_no}",
                    )
                    for page_no, (slide, slide_version) in enumerate(
                        zip(slides, slide_versions, strict=True), start=1
                    )
                ]
            )
            await db.flush()

            draft = await get_draft_version(db, course, user, create=False)
            if draft is not None:
                bump_generation(draft)

            job.status = "ready"
            job.pdf_asset_id = pdf_asset.id
            job.page_count = page_count
            job.finished_at = _now()
            await db.commit()
            ingest_lesson_version_id = lesson_version.id
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            failed = await db.get(SlideImportJob, job_id)
            if failed is not None:
                failed.status = "failed"
                failed.error = str(exc)[:1000]
                failed.finished_at = _now()
                await db.commit()
            logger.exception("Slide import job %s thất bại", job_id)
        finally:
            try:
                await asyncio.to_thread(media_storage.delete_key, source_key)
            except Exception:  # noqa: BLE001
                logger.warning("Không xoá được file staging %s", source_key)

    # Index ngay bản nháp để khóa học có thể được xuất bản khi mọi slide đã
    # sẵn sàng. Lỗi index được ghi vào slide_documents và không làm hỏng job
    # import (slide vẫn dùng được, chỉ chặn xuất bản cho tới khi index xong).
    if ingest_lesson_version_id is not None:
        try:
            from app.services import embedding

            await embedding.sync_lesson_version(
                ingest_lesson_version_id, include_draft=True
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Không index được slide cho lesson version %s",
                ingest_lesson_version_id,
                exc_info=True,
            )


async def process_pending_slide_imports(limit: int = 1) -> int:
    """Lấy job queued và xử lý; trả về số job đã nhận."""
    async with SessionLocal() as db:
        stale_before = _now() - timedelta(
            seconds=settings.content_worker_stale_seconds
        )
        await db.execute(
            update(SlideImportJob)
            .where(
                SlideImportJob.status == "processing",
                SlideImportJob.started_at < stale_before,
            )
            .values(status="queued", started_at=None)
        )
        await db.commit()

        jobs = (
            await db.execute(
                select(SlideImportJob)
                .where(SlideImportJob.status == "queued")
                .order_by(SlideImportJob.created_at)
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
        ).scalars().all()
        if not jobs:
            return 0

        job_ids = [job.id for job in jobs]
        for job in jobs:
            job.status = "processing"
            job.started_at = _now()
        await db.commit()

    for job_id in job_ids:
        await process_slide_import(job_id)
    return len(job_ids)


async def list_lesson_slides_admin(
    db: AsyncSession, course: Course, user: User, lesson_id: str
) -> list[SlideAdminOut]:
    draft, item = await _draft_item(db, course, lesson_id, user)
    lesson_version = await ensure_draft_lesson_version(db, item, user)
    rows = (
        await db.execute(
            select(
                LessonVersionSlide,
                SlideVersion,
                MediaAsset,
                SlideDocument,
            )
            .join(
                SlideVersion,
                SlideVersion.id == LessonVersionSlide.slide_version_id,
            )
            .outerjoin(
                MediaAsset,
                MediaAsset.id == SlideVersion.source_pdf_asset_id,
            )
            .outerjoin(
                SlideDocument,
                SlideDocument.slide_version_id
                == LessonVersionSlide.slide_version_id,
            )
            .where(LessonVersionSlide.lesson_version_id == lesson_version.id)
            .order_by(LessonVersionSlide.position)
            .options(
                raiseload(LessonVersionSlide.slide_version),
                raiseload(SlideVersion.source_pdf_asset),
            )
        )
    ).all()
    out: list[SlideAdminOut] = []
    for row, slide_version, asset, document in rows:
        metadata = (asset.metadata_ if asset else {}) or {}
        out.append(
            SlideAdminOut(
                id=row.id,
                order_index=row.position,
                title=row.title or f"Slide {row.position + 1}",
                pdf_url=(
                    media_storage.asset_file_url(asset.id) if asset else None
                ),
                page_number=slide_version.source_page if slide_version else 1,
                page_count=int(metadata.get("page_count") or 1),
                source_format=metadata.get("source_format"),
                embedding_status=document.ingestion_state if document else "none",
                embedding_error=document.ingestion_error if document else None,
                slide_version_id=row.slide_version_id,
                lesson_version_id=row.lesson_version_id,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Publish / outline
# ---------------------------------------------------------------------------
def _validate_questions(questions: list[dict]) -> None:
    if not isinstance(questions, list) or not questions:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "quiz_not_ready", "message": "Bài tập chưa có câu hỏi"},
        )
    seen: set[str] = set()
    for question in questions:
        qid = str(question.get("id") or "")
        if not qid or qid in seen:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"code": "quiz_not_ready", "message": "Câu hỏi thiếu ID hoặc trùng ID"},
            )
        seen.add(qid)
        options = question.get("options") or []
        option_ids = {str(option.get("id")) for option in options}
        correct = {str(item) for item in (question.get("correctOptionIds") or [])}
        if not option_ids or not correct or not correct <= option_ids:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "quiz_not_ready",
                    "message": f"Câu hỏi {qid} thiếu đáp án hợp lệ",
                },
            )
        if float(question.get("points") or 0) <= 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "quiz_not_ready",
                    "message": f"Câu hỏi {qid} phải có điểm > 0",
                },
            )


async def validate_draft(db: AsyncSession, draft: CourseVersion) -> None:
    items = (
        await db.execute(
            select(CourseVersionItem)
            .where(CourseVersionItem.course_version_id == draft.id)
            .order_by(CourseVersionItem.position)
        )
    ).scalars().all()
    for item in items:
        lesson = await db.get(
            Lesson,
            item.lesson_id,
            options=[
                raiseload(Lesson.versions),
                raiseload(Lesson.slides),
            ],
        )
        lesson_version = await db.get(
            LessonVersion,
            item.lesson_version_id,
            options=[raiseload(LessonVersion.slides)],
        )
        if lesson is None or lesson_version is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"code": "content_invalid", "message": "Item thiếu bài học/phiên bản"},
            )
        if lesson.kind == "lesson":
            slides = (
                await db.execute(
                    select(LessonVersionSlide)
                    .where(
                        LessonVersionSlide.lesson_version_id == lesson_version.id
                    )
                    .options(raiseload(LessonVersionSlide.slide_version))
                )
            ).scalars().all()
            if not slides:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "content_invalid",
                        "message": f'Bài giảng "{lesson_version.title}" chưa có slide',
                    },
                )
            slide_version_ids = list(
                dict.fromkeys(slide.slide_version_id for slide in slides)
            )
            documents = (
                await db.execute(
                    select(SlideDocument).where(
                        SlideDocument.slide_version_id.in_(slide_version_ids)
                    )
                )
            ).scalars().all()
            by_slide_version = {
                document.slide_version_id: document for document in documents
            }
            not_indexed = [
                slide_version_id
                for slide_version_id in slide_version_ids
                if (
                    by_slide_version.get(slide_version_id) is None
                    or by_slide_version[slide_version_id].ingestion_state != "ready"
                )
            ]
            if not_indexed:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "slides_not_indexed",
                        "message": (
                            f'Bài giảng "{lesson_version.title}" còn '
                            f"{len(not_indexed)} trang chưa index xong cho trợ lý "
                            "học tập. Vui lòng chờ hệ thống xử lý hoặc bấm "
                            '"Thử lại index" trong trình soạn bài giảng.'
                        ),
                    },
                )
            for slide in slides:
                slide_version = await db.get(
                    SlideVersion,
                    slide.slide_version_id,
                    options=[raiseload(SlideVersion.source_pdf_asset)],
                )
                asset = (
                    await db.get(MediaAsset, slide_version.source_pdf_asset_id)
                    if slide_version
                    else None
                )
                if asset is None or asset.state != "ready":
                    raise HTTPException(
                        status.HTTP_400_BAD_REQUEST,
                        detail={
                            "code": "content_invalid",
                            "message": f'Slide của "{lesson_version.title}" chưa sẵn sàng',
                        },
                    )
        else:
            quiz = await db.get(QuizSpec, lesson_version.id)
            if quiz is None:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "quiz_not_ready",
                        "message": f'Bài tập "{lesson_version.title}" chưa có đề',
                    },
                )
            _validate_questions(quiz.questions)


async def publish_course(
    db: AsyncSession, course: Course, user: User, expected_generation: int | None
) -> CourseVersion:
    # Khóa course để chống publish/edit đồng thời.
    await db.execute(select(Course.id).where(Course.id == course.id).with_for_update())
    draft = await get_draft_version(db, course, user)
    assert draft is not None
    check_generation(draft, expected_generation)
    await validate_draft(db, draft)

    # Publish toàn bộ lesson version đang được draft tham chiếu. View published
    # outline và chatbot chỉ đọc lesson version state='published'.
    lesson_version_ids = (
        await db.execute(
            select(CourseVersionItem.lesson_version_id)
            .where(CourseVersionItem.course_version_id == draft.id)
            .distinct()
        )
    ).scalars().all()
    for lesson_version_id in lesson_version_ids:
        lesson_version = await db.get(
            LessonVersion,
            lesson_version_id,
            options=[raiseload(LessonVersion.slides)],
        )
        if lesson_version is not None and lesson_version.state == "draft":
            lesson_version.state = "published"
            lesson_version.published_at = _now()
            lesson_version.published_by = user.id

    draft.state = "published"
    draft.published_at = _now()
    draft.published_by = user.id
    # Flush version state trước để trigger courses.published_version_id thấy
    # version đã published trong cùng transaction.
    await db.flush()
    course.published_version_id = draft.id
    course.updated_at = _now()
    db.add(
        ContentAuditEvent(
            actor_id=user.id,
            course_id=course.id,
            course_version_id=draft.id,
            action="publish",
            request_id=None,
        )
    )
    await db.flush()
    return draft


async def _outline_item_rows(db: AsyncSession, course_version_id: str):
    """Một query cho toàn bộ item + lesson + quiz + số slide của outline."""
    slide_counts = (
        select(
            LessonVersionSlide.lesson_version_id,
            func.count(LessonVersionSlide.id).label("slide_count"),
        )
        .group_by(LessonVersionSlide.lesson_version_id)
        .subquery()
    )
    return (
        await db.execute(
            select(
                CourseVersionItem,
                Lesson,
                LessonVersion,
                QuizSpec,
                func.coalesce(slide_counts.c.slide_count, 0),
            )
            .join(Lesson, Lesson.id == CourseVersionItem.lesson_id)
            .join(
                LessonVersion,
                LessonVersion.id == CourseVersionItem.lesson_version_id,
            )
            .outerjoin(QuizSpec, QuizSpec.lesson_version_id == LessonVersion.id)
            .outerjoin(
                slide_counts,
                slide_counts.c.lesson_version_id == LessonVersion.id,
            )
            .where(CourseVersionItem.course_version_id == course_version_id)
            .order_by(CourseVersionItem.position)
            .options(
                raiseload(Lesson.versions),
                raiseload(Lesson.slides),
                raiseload(LessonVersion.slides),
            )
        )
    ).all()


async def published_quiz_lesson_ids(
    db: AsyncSession, course: Course
) -> set[str]:
    """ID các bài tập đang hiển thị với sinh viên trong bản xuất bản.

    Sinh viên chỉ thấy quiz thuộc course version đã publish. Trạng thái
    `lesson_versions.state` của bản nháp không quyết định việc này: khi giáo
    viên sửa quiz, hệ thống tạo lesson version nháp mới nhưng bản đã publish
    vẫn là bản sinh viên đang thấy cho tới khi xuất bản lại.
    """
    if not course.published_version_id:
        return set()
    rows = await db.execute(
        select(CourseVersionItem.lesson_id)
        .join(Lesson, Lesson.id == CourseVersionItem.lesson_id)
        .join(
            QuizSpec,
            QuizSpec.lesson_version_id == CourseVersionItem.lesson_version_id,
        )
        .where(
            CourseVersionItem.course_version_id == course.published_version_id,
            Lesson.kind == "quiz",
        )
    )
    return set(rows.scalars().all())


async def get_draft_tree(
    db: AsyncSession, course: Course, user: User
) -> list[ModuleNodeOut]:
    draft = await get_draft_version(db, course, user)
    assert draft is not None
    modules = (
        await db.execute(
            select(CourseVersionModule)
            .where(CourseVersionModule.course_version_id == draft.id)
            .order_by(CourseVersionModule.position)
            .options(raiseload(CourseVersionModule.items))
        )
    ).scalars().all()
    rows = await _outline_item_rows(db, draft.id)
    by_module: dict[str, list] = {}
    for row in rows:
        by_module.setdefault(row[0].module_id, []).append(row)

    # Bài tập đã có trong bản xuất bản thì sinh viên đã thấy, kể cả khi giáo
    # viên đang sửa một lesson version nháp mới.
    published_quiz_lessons = await published_quiz_lesson_ids(db, course)

    # Đếm trạng thái index RAG theo từng lesson version trong một query.
    lesson_version_ids = [row[2].id for row in rows]
    ingest_counts: dict[str, tuple[int, int, int]] = {}
    if lesson_version_ids:
        count_rows = (
            await db.execute(
                select(
                    LessonVersionSlide.lesson_version_id,
                    func.count(SlideDocument.slide_version_id)
                    .filter(SlideDocument.ingestion_state == "ready")
                    .label("ready"),
                    func.count(SlideDocument.slide_version_id)
                    .filter(SlideDocument.ingestion_state == "failed")
                    .label("failed"),
                    func.count(SlideDocument.slide_version_id)
                    .filter(SlideDocument.ingestion_state == "pending")
                    .label("pending"),
                )
                .outerjoin(
                    SlideDocument,
                    SlideDocument.slide_version_id
                    == LessonVersionSlide.slide_version_id,
                )
                .where(
                    LessonVersionSlide.lesson_version_id.in_(lesson_version_ids)
                )
                .group_by(LessonVersionSlide.lesson_version_id)
            )
        ).all()
        ingest_counts = {
            row.lesson_version_id: (
                int(row.ready),
                int(row.failed),
                int(row.pending),
            )
            for row in count_rows
        }

    out: list[ModuleNodeOut] = []
    for module in modules:
        lessons: list[LessonNodeOut] = []
        for item, lesson, lesson_version, quiz, slide_count in by_module.get(
            module.id, []
        ):
            slides_ready, slides_failed, _ = ingest_counts.get(
                lesson_version.id, (0, 0, 0)
            )
            # Slide chưa có row trong slide_documents cũng coi như đang chờ
            # index để UI poll và checklist xuất bản phản ánh đúng.
            slides_pending = max(
                0, int(slide_count) - slides_ready - slides_failed
            )
            lessons.append(
                LessonNodeOut(
                    id=lesson.id,
                    title=lesson_version.title,
                    kind=lesson.kind,
                    slides=int(slide_count),
                    slides_ready=slides_ready,
                    slides_failed=slides_failed,
                    slides_pending=slides_pending,
                    quiz_id=lesson_version.id if quiz else None,
                    # Trạng thái bài tập phản ánh việc sinh viên có thấy bài
                    # trong bản xuất bản hay không, không phải state của
                    # lesson version nháp đang được sửa.
                    quiz_status=(
                        (
                            "published"
                            if lesson.id in published_quiz_lessons
                            else "draft"
                        )
                        if quiz
                        else None
                    ),
                    question_count=len(quiz.questions) if quiz else 0,
                    duration_minutes=quiz.duration_minutes if quiz else None,
                    due_at=quiz.due_at if quiz else None,
                    lesson_version_id=lesson_version.id,
                    item_id=item.id,
                )
            )
        out.append(
            ModuleNodeOut(
                id=module.id,
                title=module.title,
                lessons=lessons,
                module_key=str(module.module_key),
                generation=draft.generation,
            )
        )
    return out


async def get_published_outline(
    db: AsyncSession, course: Course
) -> CourseOutlineOut:
    published = await get_published_version(db, course)
    if published is None:
        raise _not_found("Khóa học chưa được xuất bản")
    modules = (
        await db.execute(
            select(CourseVersionModule)
            .where(CourseVersionModule.course_version_id == published.id)
            .order_by(CourseVersionModule.position)
            .options(raiseload(CourseVersionModule.items))
        )
    ).scalars().all()
    rows = await _outline_item_rows(db, published.id)
    by_module: dict[str, list] = {}
    for row in rows:
        by_module.setdefault(row[0].module_id, []).append(row)

    out_modules: list[ModuleItemOut] = []
    for module in modules:
        lessons: list[LessonItemOut] = []
        for item, lesson, lesson_version, quiz, slide_count in by_module.get(
            module.id, []
        ):
            lessons.append(
                LessonItemOut(
                    id=lesson.id,
                    title=lesson_version.title,
                    kind=lesson.kind,
                    slide_count=int(slide_count),
                    quiz_id=lesson_version.id if quiz else None,
                    quiz_status="published" if quiz else None,
                    question_count=len(quiz.questions) if quiz else 0,
                    duration_minutes=quiz.duration_minutes if quiz else None,
                    due_at=quiz.due_at if quiz else None,
                )
            )
        out_modules.append(
            ModuleItemOut(
                id=module.id,
                order_index=module.position,
                title=module.title,
                lessons=lessons,
            )
        )
    return CourseOutlineOut(
        id=course.id,
        title=published.title,
        modules=out_modules,
        show_gaze_dot=course.show_gaze_dot,
        require_calibration=course.require_calibration,
    )


def _slide_out(
    row: LessonVersionSlide,
    slide_version: SlideVersion | None,
    asset: MediaAsset | None,
) -> SlideOut:
    metadata = (asset.metadata_ if asset else {}) or {}
    return SlideOut(
        id=row.id,
        title=row.title or f"Slide {row.position + 1}",
        pdf_url=media_storage.asset_file_url(asset.id) if asset else None,
        page_number=slide_version.source_page if slide_version else 1,
        page_count=int(metadata.get("page_count") or 1),
        source_format=metadata.get("source_format"),
        slide_version_id=row.slide_version_id,
        lesson_version_id=row.lesson_version_id,
    )


async def _slide_rows(db: AsyncSession, lesson_version_id: str):
    return (
        await db.execute(
            select(LessonVersionSlide, SlideVersion, MediaAsset)
            .join(
                SlideVersion,
                SlideVersion.id == LessonVersionSlide.slide_version_id,
            )
            .outerjoin(
                MediaAsset,
                MediaAsset.id == SlideVersion.source_pdf_asset_id,
            )
            .where(LessonVersionSlide.lesson_version_id == lesson_version_id)
            .order_by(LessonVersionSlide.position)
            .options(
                raiseload(LessonVersionSlide.slide_version),
                raiseload(SlideVersion.source_pdf_asset),
            )
        )
    ).all()


async def get_lesson_version_contents(
    db: AsyncSession, lesson_version_id: str
) -> list[SlideOut]:
    rows = await _slide_rows(db, lesson_version_id)
    return [_slide_out(row, slide_version, asset) for row, slide_version, asset in rows]


async def get_lesson_contents(
    db: AsyncSession, course: Course, lesson_id: str
) -> list[SlideOut]:
    published = await get_published_version(db, course)
    if published is None:
        raise _not_found("Khóa học chưa được xuất bản")
    item = (
        await db.execute(
            select(CourseVersionItem).where(
                CourseVersionItem.course_version_id == published.id,
                CourseVersionItem.lesson_id == lesson_id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise _not_found("Không tìm thấy bài học trong bản xuất bản")
    rows = await _slide_rows(db, item.lesson_version_id)
    return [_slide_out(row, slide_version, asset) for row, slide_version, asset in rows]


async def get_course_students(
    db: AsyncSession, course: Course
) -> list[StudentRowOut]:
    from app.services import metrics

    return await metrics.course_students(db, course)
