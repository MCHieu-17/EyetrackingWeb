
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.access import get_lesson_or_404
from app.api.deps import (
    can_access_course,
    can_manage_course,
    get_current_user,
    require_roles,
)
from app.core.config import settings
from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.models.auth import User
from app.models.course import (
    Course,
    CourseVersionItem,
    Enrollment,
    Lesson,
    LessonVersion,
    LessonVersionSlide,
)
from app.schemas.course import (
    EmbeddingSyncOut,
    LessonCreateIn,
    LessonUpdateIn,
    SlideAdminOut,
    SlideImportJobOut,
    SlideKeySetIn,
    SlideKeyUpdateIn,
    SlideOut,
)
from app.schemas.gaze import OkOut
from app.services import content, embedding

router = APIRouter(tags=["lessons"])


async def _course_for_lesson(db: AsyncSession, lesson_id: str) -> tuple[Lesson, Course]:
    lesson = await get_lesson_or_404(db, lesson_id)
    course = await db.get(Course, lesson.course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    return lesson, course


@router.post(
    "/teacher/modules/{module_id}/lessons", response_model=dict, status_code=201
)
async def create_lesson(
    module_id: str,
    body: LessonCreateIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course, _ = await content.course_of_module(db, module_id)
    if not await can_manage_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    lesson = await content.create_lesson(db, course, user, module_id, body.title)
    await db.commit()
    return {"id": lesson.id, "title": body.title}


@router.patch("/teacher/lessons/{lesson_id}")
async def update_lesson(
    lesson_id: str,
    body: LessonUpdateIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    lesson, course = await _course_for_lesson(db, lesson_id)
    if not await can_manage_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    if body.title is not None:
        await content.update_lesson(db, course, user, lesson.id, body.title)
    await db.commit()
    return {"ok": True}


@router.delete("/teacher/lessons/{lesson_id}")
async def delete_lesson(
    lesson_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    lesson, course = await _course_for_lesson(db, lesson_id)
    if not await can_manage_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    await content.delete_lesson(db, course, user, lesson.id)
    await db.commit()
    return {"ok": True}


@router.post("/teacher/lessons/{lesson_id}/slides", status_code=201)
async def add_slide(
    lesson_id: str,
    body: dict,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED,
        detail="Thêm slide thủ công chưa hỗ trợ; hãy tải PDF cho bài giảng.",
    )


@router.post(
    "/teacher/lessons/{lesson_id}/slides/upload",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit(15, 60, "upload"))],
)
async def upload_lesson_slides(
    lesson_id: str,
    file: UploadFile = File(...),
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    lesson, course = await _course_for_lesson(db, lesson_id)
    if not await can_manage_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")

    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data.extend(chunk)
        if len(data) > settings.max_upload_bytes:
            limit = settings.max_upload_bytes // (1024 * 1024)
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"File vượt quá {limit}MB cho phép.",
            )

    job = await content.create_slide_import(
        db,
        course,
        user,
        lesson.id,
        bytes(data),
        file.filename or "slides",
        file.content_type,
    )
    await db.commit()
    return {"ok": True, "jobId": job.id, "status": job.status}


@router.get(
    "/teacher/lessons/{lesson_id}/slides/imports/{job_id}",
    response_model=SlideImportJobOut,
)
async def get_slide_import_job(
    lesson_id: str,
    job_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    lesson, course = await _course_for_lesson(db, lesson_id)
    if not await can_manage_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    job = await content.get_slide_import_job(db, course, lesson.id, job_id)
    return SlideImportJobOut(
        id=job.id,
        status=job.status,
        filename=job.source_filename,
        page_count=job.page_count,
        error=job.error,
        created_at=job.created_at,
        finished_at=job.finished_at,
    )


@router.delete("/teacher/slides/{slide_id}")
async def delete_slide(
    slide_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(LessonVersionSlide, slide_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy slide")
    lesson_version = await db.get(LessonVersion, row.lesson_version_id)
    lesson = await db.get(Lesson, lesson_version.lesson_id) if lesson_version else None
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài học")
    course = await db.get(Course, lesson.course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    if not await can_manage_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    await content.delete_slide(db, course, user, slide_id)
    await db.commit()
    return {"ok": True}


@router.get(
    "/teacher/lessons/{lesson_id}/slides", response_model=list[SlideAdminOut]
)
async def list_lesson_slides(
    lesson_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    lesson, course = await _course_for_lesson(db, lesson_id)
    if not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    return await content.list_lesson_slides_admin(db, course, user, lesson.id)


@router.patch("/teacher/slides/{slide_id}", response_model=OkOut)
async def set_slide_key(
    slide_id: str,
    body: SlideKeyUpdateIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(LessonVersionSlide, slide_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy slide")
    lesson_version = await db.get(LessonVersion, row.lesson_version_id)
    lesson = await db.get(Lesson, lesson_version.lesson_id) if lesson_version else None
    course = await db.get(Course, lesson.course_id) if lesson else None
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    if not await can_manage_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    await content.set_slide_key(db, course, user, slide_id, body.is_key)
    await db.commit()
    return OkOut()


@router.post("/teacher/lessons/{lesson_id}/slides/key", response_model=OkOut)
async def set_slide_keys(
    lesson_id: str,
    body: SlideKeySetIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    lesson, course = await _course_for_lesson(db, lesson_id)
    if not await can_manage_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    await content.set_slide_keys(
        db, course, user, lesson.id, body.order_indexes
    )
    await db.commit()
    return OkOut()


@router.get("/api/lessons/{lesson_id}/contents", response_model=list[SlideOut])
async def get_lesson_contents(
    lesson_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lesson, course = await _course_for_lesson(db, lesson_id)
    enrolled = (
        await db.execute(
            select(Enrollment).where(
                Enrollment.course_id == course.id,
                Enrollment.student_id == user.id,
                Enrollment.status != "dropped",
            )
        )
    ).scalar_one_or_none()
    if not await can_access_course(db, course, user) and enrolled is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Chưa đăng ký khóa học")
    return await content.get_lesson_contents(db, course, lesson.id)


@router.post(
    "/teacher/lessons/{lesson_id}/reindex",
    response_model=EmbeddingSyncOut,
    dependencies=[Depends(rate_limit(10, 60, "reindex"))],
)
async def reindex_lesson(
    lesson_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    lesson, course = await _course_for_lesson(db, lesson_id)
    if not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    if course.published_version_id is None:
        return EmbeddingSyncOut(ready=0, failed=0)
    item = (
        await db.execute(
            select(CourseVersionItem).where(
                CourseVersionItem.course_version_id == course.published_version_id,
                CourseVersionItem.lesson_id == lesson.id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        return EmbeddingSyncOut(ready=0, failed=0)
    result = await embedding.sync_lesson_version(item.lesson_version_id)
    return EmbeddingSyncOut(**result)


@router.post(
    "/teacher/courses/{course_id}/reindex",
    response_model=EmbeddingSyncOut,
    dependencies=[Depends(rate_limit(5, 60, "reindex"))],
)
async def reindex_course(
    course_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course = await db.get(Course, course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    if not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    if course.published_version_id is None:
        return EmbeddingSyncOut(ready=0, failed=0)
    result = await embedding.sync_course_version(course.published_version_id)
    return EmbeddingSyncOut(**result)


@router.post(
    "/admin/embeddings/reindex-all",
    response_model=EmbeddingSyncOut,
    dependencies=[Depends(rate_limit(2, 60, "reindex-all"))],
)
async def reindex_all(
    _: User = Depends(require_roles("admin")),
):
    result = await embedding.reindex_all()
    return EmbeddingSyncOut(**result)


@router.get("/teacher/courses/{course_id}/embedding-status")
async def embedding_status(
    course_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course = await db.get(Course, course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    if not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    if course.published_version_id is None:
        return {}
    return await embedding.course_counts(course.published_version_id)
