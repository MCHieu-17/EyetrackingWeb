
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.access import (
    get_lesson_with_course,
    get_managed_lesson,
    get_viewable_lesson,
)
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
from app.models.course import Enrollment
from app.schemas.course import (
    LessonCreateIn,
    LessonUpdateIn,
    SlideAdminOut,
    SlideImportJobOut,
    SlideOut,
)
from app.services import content, embedding, embedding_jobs

router = APIRouter(tags=["lessons"])


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
    lesson, course = await get_managed_lesson(db, lesson_id, user)
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
    lesson, course = await get_managed_lesson(db, lesson_id, user)
    removed = await content.delete_lesson(db, course, user, lesson.id)
    await db.commit()
    await content.delete_media_objects(removed)
    return {"ok": True}


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
    lesson, course = await get_managed_lesson(db, lesson_id, user)

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
    lesson, course = await get_managed_lesson(db, lesson_id, user)
    job = await content.get_slide_import_job(db, course, lesson.id, job_id)
    payload = job.payload or {}
    return SlideImportJobOut(
        id=job.id,
        status=job.status,
        filename=str(payload.get("source_filename") or ""),
        page_count=payload.get("page_count"),
        error=job.error,
        created_at=job.created_at,
        finished_at=job.finished_at,
    )


@router.get(
    "/teacher/lessons/{lesson_id}/slides", response_model=list[SlideAdminOut]
)
async def list_lesson_slides(
    lesson_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    lesson, course = await get_viewable_lesson(db, lesson_id, user)
    return await content.list_lesson_slides_admin(db, course, user, lesson.id)


@router.post("/teacher/lessons/{lesson_id}/slides/reindex")
async def reindex_lesson_slides(
    lesson_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """Index lại các slide chưa sẵn sàng của bài giảng đang soạn."""
    lesson, course = await get_managed_lesson(db, lesson_id, user)
    slides = await content.list_lesson_slides_admin(db, course, user, lesson.id)
    if not slides:
        return {"ok": True, "queued": 0}
    queued = await embedding.mark_lesson_pending(lesson.id)
    await embedding_jobs.enqueue_index_lesson(db, lesson.id, force=True)
    await db.commit()
    return {"ok": True, "queued": queued}


@router.get("/api/lessons/{lesson_id}/contents", response_model=list[SlideOut])
async def get_lesson_contents(
    lesson_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lesson, course = await get_lesson_with_course(db, lesson_id)
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
