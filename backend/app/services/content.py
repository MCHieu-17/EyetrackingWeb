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
from typing import Iterable

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.auth import User
from app.models.course import (
    ContentAuditEvent,
    Course,
    CourseVersion,
    CourseVersionItem,
    CourseVersionModule,
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
from app.services import media_storage, slide_import

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
    course = await db.get(Course, course_id)
    if course is None:
        raise _not_found("Không tìm thấy khóa học")
    return course


async def get_published_version(
    db: AsyncSession, course: Course
) -> CourseVersion | None:
    if not course.published_version_id:
        return None
    return await db.get(CourseVersion, course.published_version_id)


async def get_draft_version(
    db: AsyncSession, course: Course, user: User, *, create: bool = True
) -> CourseVersion | None:
    stmt = select(CourseVersion).where(
        CourseVersion.course_id == course.id,
        CourseVersion.state == "draft",
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
                is_key=slide.is_key,
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
    lesson_version = await db.get(LessonVersion, item.lesson_version_id)
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
    module = await db.get(CourseVersionModule, module_id)
    if module is None:
        raise _not_found("Không tìm thấy chương")
    version = await db.get(CourseVersion, module.course_version_id)
    if version is None:
        raise _not_found("Không tìm thấy phiên bản khóa học")
    course = await db.get(Course, version.course_id)
    if course is None:
        raise _not_found("Không tìm thấy khóa học")
    return course, module


async def _draft_module(
    db: AsyncSession, course: Course, module_id: str, user: User
) -> tuple[CourseVersion, CourseVersionModule]:
    draft = await get_draft_version(db, course, user)
    assert draft is not None
    module = await db.get(CourseVersionModule, module_id)
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
    by_id = {item.id: item for item in items}
    for index, item in enumerate(items):
        item.position = -index - 1
    await db.flush()
    for index, item_id in enumerate(ordered_ids):
        by_id[item_id].position = index
    await db.flush()


async def _renumber_slides(
    db: AsyncSession, lesson_version_id: str, ordered_ids: list[str]
) -> None:
    slides = (
        await db.execute(
            select(LessonVersionSlide).where(
                LessonVersionSlide.lesson_version_id == lesson_version_id
            )
        )
    ).scalars().all()
    by_id = {slide.id: slide for slide in slides}
    for index, slide in enumerate(slides):
        slide.position = -index - 1
    await db.flush()
    for index, slide_id in enumerate(ordered_ids):
        by_id[slide_id].position = index
    await db.flush()


# ---------------------------------------------------------------------------
# Course list / create / metadata
# ---------------------------------------------------------------------------
async def list_teacher_courses(
    db: AsyncSession, user: User, *, status_filter: str | None = None, q: str | None = None
) -> list[TeacherCourseOut]:
    from app.models.course import CourseTeacher

    if "admin" in user.role_codes:
        stmt = select(Course)
    else:
        assigned = select(CourseTeacher.course_id).where(
            CourseTeacher.teacher_id == user.id
        )
        stmt = select(Course).where(
            (Course.owner_id == user.id) | Course.id.in_(assigned)
        )
    if q:
        stmt = stmt.where(Course.id.in_(select(CourseVersion.course_id).where(
            CourseVersion.title.ilike(f"%{q}%")
        )))
    courses = list((await db.execute(stmt.order_by(Course.updated_at.desc()))).scalars().all())
    if not courses:
        return []

    from app.services import course_stats

    course_ids = [course.id for course in courses]
    enroll_counts = await course_stats.enrollment_counts(db, course_ids)
    attention = await course_stats.attention_avg_by_course(db, course_ids)
    sessions = await course_stats.session_counts_by_course(db, course_ids)

    out: list[TeacherCourseOut] = []
    for course in courses:
        published = await get_published_version(db, course)
        draft = await get_draft_version(db, course, user, create=False)
        version = published or draft
        if version is None:
            continue
        item_count = (
            await db.execute(
                select(func.count(CourseVersionItem.id)).where(
                    CourseVersionItem.course_version_id == version.id
                )
            )
        ).scalar_one()
        status_value = (
            "archived"
            if course.archived_at is not None
            else "published"
            if published is not None
            else "draft"
        )
        if status_filter and status_value != status_filter:
            continue
        out.append(
            TeacherCourseOut(
                id=course.id,
                title=version.title,
                description=version.description or "",
                gradient="",
                status=status_value,
                students=enroll_counts.get(course.id, 0),
                attention=attention.get(course.id),
                sessions=sessions.get(course.id, 0),
                updated_at=course.updated_at,
                is_owner="admin" in user.role_codes or course.owner_id == user.id,
                lesson_count=int(item_count),
                show_gaze_dot=course.show_gaze_dot,
                require_calibration=course.require_calibration,
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

        try:
            data = await asyncio.to_thread(media_storage.get_bytes, source_key)
            fmt = slide_import.detect_format(
                job.source_filename, job.source_mime, data
            )
            pdf_bytes = await asyncio.to_thread(
                slide_import.convert_to_pdf, data, fmt, job.source_filename
            )
            page_count = slide_import.validate_pdf(pdf_bytes)

            course = await db.get(Course, job.course_id)
            user = await db.get(User, job.created_by)
            lesson_version = await db.get(LessonVersion, job.lesson_version_id)
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
            for page_no in range(1, page_count + 1):
                slide = Slide(lesson_id=job.lesson_id)
                db.add(slide)
                await db.flush()
                slide_version = SlideVersion(
                    slide_id=slide.id,
                    revision_no=1,
                    source_pdf_asset_id=pdf_asset.id,
                    source_page=page_no,
                    render_metadata={
                        "converter": "libreoffice",
                        "source_format": fmt,
                        "page_count": page_count,
                    },
                    created_by=job.created_by,
                )
                db.add(slide_version)
                await db.flush()
                db.add(
                    LessonVersionSlide(
                        lesson_version_id=lesson_version.id,
                        slide_id=slide.id,
                        slide_version_id=slide_version.id,
                        position=page_no - 1,
                        title=f"Slide {page_no}",
                        is_key=False,
                    )
                )

            draft = await get_draft_version(db, course, user, create=False)
            if draft is not None:
                bump_generation(draft)

            job.status = "ready"
            job.pdf_asset_id = pdf_asset.id
            job.page_count = page_count
            job.finished_at = _now()
            await db.commit()
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
            select(LessonVersionSlide)
            .where(LessonVersionSlide.lesson_version_id == lesson_version.id)
            .order_by(LessonVersionSlide.position)
        )
    ).scalars().all()
    out: list[SlideAdminOut] = []
    for row in rows:
        slide_version = await db.get(SlideVersion, row.slide_version_id)
        asset = (
            await db.get(MediaAsset, slide_version.source_pdf_asset_id)
            if slide_version
            else None
        )
        document = await db.get(SlideDocument, row.slide_version_id)
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
                is_key=row.is_key,
                embedding_status=document.ingestion_state if document else "none",
                embedding_error=document.ingestion_error if document else None,
                slide_version_id=row.slide_version_id,
                lesson_version_id=row.lesson_version_id,
            )
        )
    return out


async def set_slide_key(
    db: AsyncSession, course: Course, user: User, membership_id: str, is_key: bool
) -> None:
    draft = await get_draft_version(db, course, user)
    assert draft is not None
    row = await db.get(LessonVersionSlide, membership_id)
    if row is None:
        raise _not_found("Không tìm thấy slide")
    lesson_version = await db.get(LessonVersion, row.lesson_version_id)
    item = (
        await db.execute(
            select(CourseVersionItem).where(
                CourseVersionItem.course_version_id == draft.id,
                CourseVersionItem.lesson_version_id == row.lesson_version_id,
            )
        )
    ).scalar_one_or_none()
    if item is None or lesson_version is None:
        raise _not_found("Không tìm thấy slide trong bản nháp")
    row.is_key = is_key
    bump_generation(draft)
    await db.flush()


async def set_slide_keys(
    db: AsyncSession,
    course: Course,
    user: User,
    lesson_id: str,
    order_indexes: Iterable[int],
) -> None:
    draft, item = await _draft_item(db, course, lesson_id, user)
    lesson_version = await ensure_draft_lesson_version(db, item, user)
    key_set = set(order_indexes)
    rows = (
        await db.execute(
            select(LessonVersionSlide).where(
                LessonVersionSlide.lesson_version_id == lesson_version.id
            )
        )
    ).scalars().all()
    for row in rows:
        row.is_key = row.position in key_set
    bump_generation(draft)
    await db.flush()


async def delete_slide(
    db: AsyncSession, course: Course, user: User, membership_id: str
) -> None:
    draft = await get_draft_version(db, course, user)
    assert draft is not None
    row = await db.get(LessonVersionSlide, membership_id)
    if row is None:
        raise _not_found("Không tìm thấy slide")
    item = (
        await db.execute(
            select(CourseVersionItem).where(
                CourseVersionItem.course_version_id == draft.id,
                CourseVersionItem.lesson_version_id == row.lesson_version_id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise _not_found("Không tìm thấy slide trong bản nháp")
    await db.delete(row)
    bump_generation(draft)
    await db.flush()


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
        lesson = await db.get(Lesson, item.lesson_id)
        lesson_version = await db.get(LessonVersion, item.lesson_version_id)
        if lesson is None or lesson_version is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"code": "content_invalid", "message": "Item thiếu bài học/phiên bản"},
            )
        if lesson.kind == "lesson":
            slides = (
                await db.execute(
                    select(LessonVersionSlide).where(
                        LessonVersionSlide.lesson_version_id == lesson_version.id
                    )
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
            for slide in slides:
                slide_version = await db.get(SlideVersion, slide.slide_version_id)
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
        lesson_version = await db.get(LessonVersion, lesson_version_id)
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
        )
    ).scalars().all()
    out: list[ModuleNodeOut] = []
    for module in modules:
        items = (
            await db.execute(
                select(CourseVersionItem)
                .where(CourseVersionItem.module_id == module.id)
                .order_by(CourseVersionItem.position)
            )
        ).scalars().all()
        lessons: list[LessonNodeOut] = []
        for item in items:
            lesson = await db.get(Lesson, item.lesson_id)
            lesson_version = await db.get(LessonVersion, item.lesson_version_id)
            if lesson is None or lesson_version is None:
                continue
            slide_count = (
                await db.execute(
                    select(func.count(LessonVersionSlide.id)).where(
                        LessonVersionSlide.lesson_version_id == lesson_version.id
                    )
                )
            ).scalar_one()
            quiz = await db.get(QuizSpec, lesson_version.id)
            lessons.append(
                LessonNodeOut(
                    id=lesson.id,
                    title=lesson_version.title,
                    kind=lesson.kind,
                    slides=int(slide_count),
                    quiz_id=lesson_version.id if quiz else None,
                    quiz_status="draft" if quiz else None,
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
        )
    ).scalars().all()
    out_modules: list[ModuleItemOut] = []
    for module in modules:
        items = (
            await db.execute(
                select(CourseVersionItem)
                .where(CourseVersionItem.module_id == module.id)
                .order_by(CourseVersionItem.position)
            )
        ).scalars().all()
        lessons: list[LessonItemOut] = []
        for item in items:
            lesson = await db.get(Lesson, item.lesson_id)
            lesson_version = await db.get(LessonVersion, item.lesson_version_id)
            if lesson is None or lesson_version is None:
                continue
            slide_count = (
                await db.execute(
                    select(func.count(LessonVersionSlide.id)).where(
                        LessonVersionSlide.lesson_version_id == lesson_version.id
                    )
                )
            ).scalar_one()
            quiz = await db.get(QuizSpec, lesson_version.id)
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


async def get_lesson_version_contents(
    db: AsyncSession, lesson_version_id: str
) -> list[SlideOut]:
    rows = (
        await db.execute(
            select(LessonVersionSlide)
            .where(LessonVersionSlide.lesson_version_id == lesson_version_id)
            .order_by(LessonVersionSlide.position)
        )
    ).scalars().all()
    out: list[SlideOut] = []
    for row in rows:
        slide_version = await db.get(SlideVersion, row.slide_version_id)
        asset = (
            await db.get(MediaAsset, slide_version.source_pdf_asset_id)
            if slide_version
            else None
        )
        out.append(_slide_out(row, slide_version, asset))
    return out


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
    rows = (
        await db.execute(
            select(LessonVersionSlide)
            .where(LessonVersionSlide.lesson_version_id == item.lesson_version_id)
            .order_by(LessonVersionSlide.position)
        )
    ).scalars().all()
    out: list[SlideOut] = []
    for row in rows:
        slide_version = await db.get(SlideVersion, row.slide_version_id)
        asset = (
            await db.get(MediaAsset, slide_version.source_pdf_asset_id)
            if slide_version
            else None
        )
        out.append(_slide_out(row, slide_version, asset))
    return out


async def get_course_students(
    db: AsyncSession, course: Course
) -> list[StudentRowOut]:
    from app.services import metrics

    return await metrics.course_students(db, course)
