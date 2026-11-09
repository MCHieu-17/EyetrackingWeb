from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.access import escape_like, validate_uuid
from app.api.deps import require_roles
from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.models.auth import Role, User, UserRole
from app.models.profile import StudentProfile, TeacherProfile, UserProfile
from app.schemas.admin import PromoteStudentIn, PromoteStudentOut, StudentAdminOut

router = APIRouter(prefix="/admin", tags=["admin"])


async def _next_teacher_code(db: AsyncSession) -> str:
    """Sinh mã giảng viên kế tiếp dạng GV0001, GV0002, ..."""
    rows = await db.execute(
        select(TeacherProfile.teacher_code).where(
            TeacherProfile.teacher_code.like("GV%")
        )
    )
    max_number = 0
    for code in rows.scalars():
        suffix = code[2:]
        if suffix.isdigit():
            max_number = max(max_number, int(suffix))
    return f"GV{max_number + 1:04d}"


@router.get("/students", response_model=list[StudentAdminOut])
async def list_students(
    q: str | None = Query(default=None, max_length=100),
    _: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Danh sách sinh viên đang hoạt động để admin nâng cấp lên giáo viên."""
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
        like = f"%{escape_like(q.strip())}%"
        stmt = stmt.where(
            or_(
                UserProfile.full_name.ilike(like, escape="\\"),
                User.email.ilike(like, escape="\\"),
                StudentProfile.student_code.ilike(like, escape="\\"),
            )
        )
    rows = (await db.execute(stmt)).all()
    return [
        StudentAdminOut(
            id=user.id,
            name=profile.full_name if profile else user.email,
            email=user.email,
            student_code=student.student_code if student else None,
            program=student.program if student else None,
            avatar_url=profile.avatar_url if profile else None,
            created_at=user.created_at,
        )
        for user, profile, student in rows
    ]


@router.post(
    "/students/{user_id}/promote",
    response_model=PromoteStudentOut,
    dependencies=[Depends(rate_limit(20, 60, "admin_promote"))],
)
async def promote_student(
    user_id: str,
    body: PromoteStudentIn,
    _: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Nâng cấp một sinh viên thành giáo viên (bỏ role student)."""
    validate_uuid(user_id, detail="Không tìm thấy sinh viên")
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Không tìm thấy sinh viên"
        )
    if user.status != "active":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Tài khoản không hoạt động"
        )

    role_codes = set(user.role_codes)
    if "teacher" in role_codes:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Tài khoản đã là giáo viên"
        )
    if "student" not in role_codes:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Tài khoản không phải sinh viên"
        )

    teacher_code = (body.teacher_code or "").strip()
    if teacher_code:
        if len(teacher_code) > 30:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Mã giảng viên quá dài"
            )
        existing = (
            await db.execute(
                select(TeacherProfile.user_id).where(
                    TeacherProfile.teacher_code == teacher_code
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="Mã giảng viên đã tồn tại"
            )
    else:
        teacher_code = await _next_teacher_code(db)

    teacher_role_id = (
        await db.execute(select(Role.id).where(Role.code == "teacher"))
    ).scalar_one()
    student_role_id = (
        await db.execute(select(Role.id).where(Role.code == "student"))
    ).scalar_one()

    department = (
        body.department.strip()
        if body.department and body.department.strip()
        else None
    )

    try:
        teacher_profile = await db.get(TeacherProfile, user.id)
        if teacher_profile is None:
            db.add(
                TeacherProfile(
                    user_id=user.id,
                    teacher_code=teacher_code,
                    department=department,
                )
            )
        else:
            teacher_profile.teacher_code = teacher_code
            if department is not None:
                teacher_profile.department = department

        db.add(UserRole(user_id=user.id, role_id=teacher_role_id))
        await db.execute(
            delete(UserRole).where(
                UserRole.user_id == user.id,
                UserRole.role_id == student_role_id,
            )
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Mã giảng viên đã tồn tại, vui lòng chọn mã khác",
        )

    return PromoteStudentOut(ok=True, teacher_code=teacher_code)
