
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.access import get_course_or_404, get_lesson_or_404
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
    Enrollment,
    Lesson,
)
from app.schemas.course import (
    LessonCreateIn,
    LessonUpdateIn,
    SlideAdminOut,
    SlideImportJobOut,
    SlideOut,
)
from app.services import content, embedding

router = APIRouter(tags=["lessons"])


async def _course_for_lesson(db: AsyncSession, lesson_id: str) -> tuple[Lesson, Course]:
    lesson = await get_lesson_or_404(db, lesson_id)
    course = await get_course_or_404(db, lesson.course_id)
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
    slides = await content.list_lesson_slides_admin(db, course, user, lesson.id)
    # Hàm trên có thể clone lesson version (copy-on-write); phải commit để
    # các request sau (và worker index) thấy cùng một bản nháp.
    await db.commit()
    return slides


@router.post("/teacher/lessons/{lesson_id}/slides/reindex")
async def reindex_lesson_slides(
    lesson_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """Index lại các slide chưa sẵn sàng của bài giảng đang soạn."""
    lesson, course = await _course_for_lesson(db, lesson_id)
    if not await can_manage_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    slides = await content.list_lesson_slides_admin(db, course, user, lesson.id)
    await db.commit()
    if not slides:
        return {"ok": True, "queued": 0}
    lesson_version_id = slides[0].lesson_version_id
    queued = await embedding.mark_lesson_version_pending(lesson_version_id)
    background_tasks.add_task(
        embedding.sync_lesson_version, lesson_version_id, True, True
    )
    return {"ok": True, "queued": queued}


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
