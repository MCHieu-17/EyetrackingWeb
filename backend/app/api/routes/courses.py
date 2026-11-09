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
from app.api.deps import can_access_course, get_current_user, require_roles
from app.core.helpers import color_for
from app.db.session import get_db
from app.models.auth import User
from app.models.course import (
    Enrollment,
)
from app.models.profile import StudentProfile, UserProfile
from app.schemas.course import (
    CourseCreateIn,
    CourseGazeDotIn,
    CourseOutlineOut,
    CourseRequireCalibrationIn,
    CourseUpdateIn,
    ModuleNodeOut,
    PublishIn,
    StudentDirectoryOut,
    StudentRowOut,
    StudentsAddIn,
    TeacherCourseOut,
)
from app.services import content, embedding, embedding_jobs

router = APIRouter(tags=["courses"])


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
    draft = await content.get_draft_version(db, course, user)
    assert draft is not None
    return TeacherCourseOut(
        id=course.id,
        title=draft.title,
        description=draft.description or "",
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
    draft = await content.update_course_metadata(
        db,
        course,
        user,
        title=data.get("title"),
        description=data.get("description"),
        show_gaze_dot=data.get("show_gaze_dot"),
        require_calibration=data.get("require_calibration"),
        archived=(data.get("status") == "archived") if data.get("status") else None,
    )
    await db.commit()
    await db.refresh(course)
    published = await content.get_published_version(db, course)
    return TeacherCourseOut(
        id=course.id,
        title=(published or draft).title,
        description=(published or draft).description or "",
        gradient="",
        status=(
            "archived"
            if course.archived_at is not None
            else "published"
            if published is not None
            else "draft"
        ),
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
    await db.commit()
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
    tree = await content.get_draft_tree(db, course, user)
    # get_draft_tree có thể tạo draft version mới; commit để request sau dùng lại.
    await db.commit()
    return tree


@router.get("/teacher/courses/{course_id}/draft", response_model=list[ModuleNodeOut])
async def get_course_draft(
    course_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_viewable_course(db, course_id, user)
    tree = await content.get_draft_tree(db, course, user)
    await db.commit()
    return tree


@router.post("/teacher/courses/{course_id}/publish")
async def publish_course(
    course_id: str,
    body: PublishIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_owned_course(db, course_id, user)
    draft = await content.get_draft_version(db, course, user)
    assert draft is not None

    # Chặn xuất bản khi còn slide chưa index xong cho trợ lý học tập. Đồng thời
    # đưa các slide còn thiếu vào hàng đợi để lần bấm sau thành công.
    stats = await embedding.course_version_ingest_status_in_session(db, draft.id)
    if stats["total"] and stats["ready"] < stats["total"]:
        await embedding.mark_course_version_pending_in_session(db, draft.id)
        await embedding_jobs.enqueue_course_version(
            db, draft.id, include_draft=True, force=True
        )
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

    version = await content.publish_course(
        db, course, user, body.expected_generation
    )
    await db.commit()
    # Lưới an toàn: sau khi publish, index nốt slide nào còn thiếu (thường không
    # còn vì đã chặn ở trên).
    await embedding_jobs.enqueue_course_version(
        db, version.id, include_draft=False, force=True
    )
    await db.commit()
    return {"ok": True, "courseVersionId": version.id}


@router.get("/teacher/courses/{course_id}/students", response_model=list[StudentRowOut])
async def get_course_students(
    course_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_viewable_course(db, course_id, user)
    return await content.get_course_students(db, course)


@router.get("/teacher/students", response_model=list[StudentDirectoryOut])
async def list_student_directory(
    q: str | None = Query(default=None, max_length=100),
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(User, UserProfile, StudentProfile)
        .outerjoin(UserProfile, UserProfile.user_id == User.id)
        .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
        .where(
            User.deleted_at.is_(None),
            User.status == "active",
            User.roles.any(code="student"),
        )
        .order_by(UserProfile.full_name)
        .limit(200)
    )
    if q and q.strip():
        esc = escape_like(q.strip())
        like = f"%{esc}%"
        stmt = stmt.where(
            or_(
                UserProfile.full_name.ilike(like, escape="\\"),
                StudentProfile.student_code.ilike(like, escape="\\"),
                User.email.ilike(like, escape="\\"),
            )
        )
    rows = (await db.execute(stmt)).all()
    return [
        StudentDirectoryOut(
            id=u.id,
            name=p.full_name if p else u.email,
            code=sp.student_code if sp else "",
            email=u.email,
            color=color_for(u.id),
        )
        for u, p, sp in rows
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
        User.roles.any(code="student"),
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
    return {"ok": True, "added": added}


@router.delete("/teacher/courses/{course_id}/students/{student_id}")
async def remove_course_student(
    course_id: str,
    student_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_viewable_course(db, course_id, user)
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
    return {"ok": True}


@router.get("/api/courses/{course_id}", response_model=CourseOutlineOut)
async def get_course_outline(
    course_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    course = await get_course_or_404(db, course_id)
    enrolled = (
        await db.execute(
            select(Enrollment).where(
                Enrollment.course_id == course.id, Enrollment.student_id == user.id
            )
        )
    ).scalar_one_or_none()
    is_owner = await can_access_course(db, course, user)
    if not is_owner and enrolled is None:
        # Khóa đã publish được phép xem outline để sinh viên quyết định đăng ký.
        if course.published_version_id is None or course.archived_at is not None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    return await content.get_published_outline(db, course)
