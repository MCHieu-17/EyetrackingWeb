from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.access import (
    escape_like,
    get_course_or_404,
    get_owned_course,
    get_viewable_course,
)
from app.api.deps import get_current_user, require_roles
from app.core.helpers import color_for
from app.core.rediscache import delete_many, get_json, set_json
from app.db.session import get_db
from app.models.auth import User
from app.models.course import Enrollment
from app.models.profile import StudentProfile
from app.schemas.course import (
    CourseCreateIn,
    CourseGazeDotIn,
    CourseOutlineOut,
    CourseRequireCalibrationIn,
    CourseUpdateIn,
    ModuleNodeOut,
    StudentDirectoryOut,
    StudentLessonOut,
    StudentRowOut,
    StudentsAddIn,
    TeacherCourseOut,
)
from app.services import content, course_stats, embedding, embedding_jobs
from app.services.access import course_access_cached, course_access_key

router = APIRouter(tags=["courses"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _invalidate_enrollment_cache(
    db: AsyncSession, course_id: str, student_ids: list[str] | None = None
) -> None:
    """Xóa cache enrollment/access/roster liên quan trong một pipeline.

    `/api/me/enrollments` cache 30s và trả kèm `requireCalibration`; không xóa
    thì sinh viên còn thấy link cũ (prepare vs vào thẳng) sau khi giáo viên đổi.
    `student_ids=None` → lấy toàn bộ enrollment của khóa.
    """
    if student_ids is None:
        student_ids = list(
            (
                await db.execute(
                    select(Enrollment.student_id).where(
                        Enrollment.course_id == course_id
                    )
                )
            )
            .scalars()
            .all()
        )
    keys = [f"course:students:{course_id}"]
    for student_id in student_ids:
        keys.append(f"student:enrollments:{student_id}")
        keys.append(course_access_key(student_id, course_id))
    await delete_many(keys)


@router.get("/teacher/courses", response_model=list[TeacherCourseOut])
async def list_teacher_courses(
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    return await content.list_teacher_courses(
        db,
        user,
        status_filter=status_filter,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.post("/teacher/courses", response_model=TeacherCourseOut, status_code=201)
async def create_course(
    body: CourseCreateIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course = await content.create_course(
        db,
        user,
        title=body.title,
        description=body.description,
        show_gaze_dot=body.show_gaze_dot,
        require_calibration=body.require_calibration,
    )
    await db.commit()
    await db.refresh(course)
    return TeacherCourseOut(
        id=course.id,
        title=course.title,
        description=course.description or "",
        gradient="",
        status="draft",
        students=0,
        attention=None,
        sessions=0,
        updated_at=course.updated_at,
        is_owner=True,
        lesson_count=0,
        show_gaze_dot=course.show_gaze_dot,
        require_calibration=course.require_calibration,
    )


@router.patch("/teacher/courses/{course_id}", response_model=TeacherCourseOut)
async def update_course(
    course_id: str,
    body: CourseUpdateIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_owned_course(db, course_id, user)
    data = body.model_dump(exclude_unset=True)
    await content.update_course_metadata(
        db,
        course,
        user,
        title=data.get("title"),
        description=data.get("description"),
        show_gaze_dot=data.get("show_gaze_dot"),
        require_calibration=data.get("require_calibration"),
        status=data.get("status"),
    )
    await db.commit()
    await db.refresh(course)
    if data.get("require_calibration") is not None:
        await _invalidate_enrollment_cache(db, course.id)
    return TeacherCourseOut(
        id=course.id,
        title=course.title,
        description=course.description or "",
        gradient="",
        status=course.status,
        students=0,
        attention=None,
        sessions=0,
        updated_at=course.updated_at,
        is_owner=True,
        lesson_count=0,
        show_gaze_dot=course.show_gaze_dot,
        require_calibration=course.require_calibration,
    )


@router.patch("/teacher/courses/{course_id}/gaze-dot", response_model=dict)
async def set_course_gaze_dot(
    course_id: str,
    body: CourseGazeDotIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_owned_course(db, course_id, user)
    course.show_gaze_dot = body.show_gaze_dot
    # Cache outline dùng `course.updated_at` trong key; bump để sinh viên
    # refresh là thấy cờ mới thay vì bản cache 60s.
    course.updated_at = _now()
    await db.commit()
    return {"ok": True, "showGazeDot": course.show_gaze_dot}


@router.patch("/teacher/courses/{course_id}/require-calibration", response_model=dict)
async def set_course_require_calibration(
    course_id: str,
    body: CourseRequireCalibrationIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_owned_course(db, course_id, user)
    course.require_calibration = body.require_calibration
    # Cache outline dùng `course.updated_at` trong key; bump để sinh viên
    # refresh là thấy cờ mới thay vì bản cache 60s.
    course.updated_at = _now()
    await db.commit()
    await _invalidate_enrollment_cache(db, course.id)
    return {"ok": True, "requireCalibration": course.require_calibration}


@router.delete("/teacher/courses/{course_id}")
async def delete_course(
    course_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_owned_course(db, course_id, user)
    await content.delete_course(db, course)
    await db.commit()
    return {"ok": True}


@router.get("/teacher/courses/{course_id}", response_model=list[ModuleNodeOut])
async def get_course_tree(
    course_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_viewable_course(db, course_id, user)
    return await content.get_course_tree(db, course, user)


@router.post("/teacher/courses/{course_id}/publish")
async def publish_course(
    course_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_owned_course(db, course_id, user)

    # Chặn xuất bản khi còn slide chưa index xong cho trợ lý học tập. Đồng thời
    # đưa các slide còn thiếu vào hàng đợi để lần bấm sau thành công.
    stats = await embedding.course_ingest_status_in_session(db, course.id)
    if stats["total"] and stats["ready"] < stats["total"]:
        await embedding.mark_course_pending_in_session(db, course.id)
        await embedding_jobs.enqueue_course_index(db, course.id, force=True)
        await db.commit()
        remaining = stats["total"] - stats["ready"]
        # Không dùng `raise HTTPException` ở đây: response 409 vẫn phải giữ
        # job đã enqueue để worker index nốt các slide còn thiếu.
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": {
                    "code": "slides_not_indexed",
                    "message": (
                        f"Còn {remaining} trang chưa index xong cho trợ lý học "
                        "tập. Hệ thống đang xử lý, vui lòng thử lại sau ít phút."
                    ),
                }
            },
        )

    await content.publish_course(db, course, user)
    await db.commit()
    await course_stats.invalidate_course_stats(course.id)
    return {"ok": True}


@router.get("/teacher/courses/{course_id}/students", response_model=list[StudentRowOut])
async def get_course_students(
    course_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_viewable_course(db, course_id, user)
    return await content.get_course_students(db, course)


@router.get(
    "/teacher/courses/{course_id}/students/{student_id}/lessons",
    response_model=list[StudentLessonOut],
)
async def get_course_student_lessons(
    course_id: str,
    student_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_viewable_course(db, course_id, user)
    lessons = await content.get_course_student_lessons(db, course, student_id)
    if lessons is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Học viên chưa đăng ký khóa học này"
        )
    return lessons


@router.get("/teacher/students", response_model=list[StudentDirectoryOut])
async def list_student_directory(
    q: str | None = Query(default=None, max_length=100),
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(User, StudentProfile)
        .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
        .where(
            User.deleted_at.is_(None),
            User.status == "active",
            User.role == "student",
        )
        .order_by(User.full_name)
        .limit(200)
    )
    if q and q.strip():
        esc = escape_like(q.strip())
        like = f"%{esc}%"
        stmt = stmt.where(
            or_(
                User.full_name.ilike(like, escape="\\"),
                StudentProfile.student_code.ilike(like, escape="\\"),
                User.email.ilike(like, escape="\\"),
            )
        )
    rows = (await db.execute(stmt)).all()
    return [
        StudentDirectoryOut(
            id=u.id,
            name=u.full_name or u.email,
            code=sp.student_code if sp else "",
            email=u.email,
            color=color_for(u.id),
        )
        for u, sp in rows
    ]


@router.post("/teacher/courses/{course_id}/students", status_code=201)
async def add_course_students(
    course_id: str,
    body: StudentsAddIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_owned_course(db, course_id, user)
    ids = list(dict.fromkeys(body.student_ids))
    if not ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Chưa chọn học viên nào")

    valid_stmt = select(User.id).where(
        User.id.in_(ids),
        User.deleted_at.is_(None),
        User.status == "active",
        User.role == "student",
    )
    valid_ids = set((await db.execute(valid_stmt)).scalars().all())

    existing_stmt = select(Enrollment).where(
        Enrollment.course_id == course.id, Enrollment.student_id.in_(valid_ids)
    )
    existing = {e.student_id: e for e in (await db.execute(existing_stmt)).scalars().all()}

    added = 0
    for sid in valid_ids:
        enr = existing.get(sid)
        if enr is not None:
            if enr.status != "active":
                enr.status = "active"
                added += 1
            continue
        db.add(Enrollment(course_id=course.id, student_id=sid))
        added += 1
    await db.commit()
    await _invalidate_enrollment_cache(db, course.id, student_ids=list(valid_ids))
    await course_stats.invalidate_course_stats(course.id)
    return {"ok": True, "added": added}


@router.delete("/teacher/courses/{course_id}/students/{student_id}")
async def remove_course_student(
    course_id: str,
    student_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_owned_course(db, course_id, user)
    enrollment = (
        await db.execute(
            select(Enrollment).where(
                Enrollment.course_id == course.id, Enrollment.student_id == student_id
            )
        )
    ).scalar_one_or_none()
    if enrollment is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Học viên chưa đăng ký khóa học này"
        )
    enrollment.status = "dropped"
    await db.commit()
    await _invalidate_enrollment_cache(db, course.id, student_ids=[student_id])
    await course_stats.invalidate_course_stats(course.id)
    return {"ok": True}


@router.get("/api/courses/{course_id}", response_model=CourseOutlineOut)
async def get_course_outline(
    course_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    course = await get_course_or_404(db, course_id)
    access = await course_access_cached(db, course, user)
    if not access["allowed"] and not access["enrolled"]:
        # Khóa đã publish được phép xem outline để sinh viên quyết định đăng ký.
        if course.status != "published":
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")

    cache_key = (
        f"course:outline:{course.id}:{course.status}:"
        f"{course.updated_at.isoformat() if course.updated_at else ''}"
    )
    cached = await get_json(cache_key)
    if isinstance(cached, dict):
        return CourseOutlineOut.model_validate(cached)

    outline = await content.get_published_outline(db, course)
    await set_json(cache_key, outline.model_dump(mode="json"), 60)
    return outline
