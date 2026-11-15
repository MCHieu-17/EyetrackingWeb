from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.crud import profile as profile_crud
from app.crud import user as user_crud
from app.db.session import get_db
from app.models.auth import User
from app.schemas.user import ProfileOut, ProfileUpdate

router = APIRouter(prefix="/api/me", tags=["me"])


async def _build_profile(db: AsyncSession, user: User) -> ProfileOut:
    full_user = await user_crud.get_user_by_id(db, user.id)
    if full_user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Tài khoản không hợp lệ"
        )
    data = ProfileOut(
        role=full_user.role,
        email=full_user.email,
        full_name=full_user.full_name,
        date_of_birth=full_user.date_of_birth,
        gender=full_user.gender,
        phone=full_user.phone,
        avatar_url=full_user.avatar_url,
        created_at=full_user.created_at,
        has_password=full_user.password_hash is not None,
    )
    if full_user.role == "student":
        sp = await profile_crud.get_student_profile(db, user.id)
        if sp:
            data.student_code = sp.student_code
            data.program = sp.program
    elif full_user.role == "teacher":
        tp = await profile_crud.get_teacher_profile(db, user.id)
        if tp:
            data.teacher_code = tp.teacher_code
            data.department = tp.department
    return data


@router.get("/profile", response_model=ProfileOut)
async def get_my_profile(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await _build_profile(db, user)


@router.patch("/profile", response_model=ProfileOut)
async def update_my_profile(
    body: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await profile_crud.upsert_user_profile(
        db,
        user_id=user.id,
        full_name=body.full_name,
        date_of_birth=body.date_of_birth,
        gender=body.gender,
        phone=body.phone,
        avatar_url=body.avatar_url,
    )
    full_user = await user_crud.get_user_by_id(db, user.id)
    if full_user is not None:
        if full_user.role == "student" and body.program is not None:
            sp = await profile_crud.get_student_profile(db, user.id)
            if sp:
                sp.program = body.program
        if full_user.role == "teacher" and body.department is not None:
            tp = await profile_crud.get_teacher_profile(db, user.id)
            if tp:
                tp.department = body.department
    await db.commit()
    refreshed = await user_crud.get_user_by_id(db, user.id)
    if refreshed is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Tài khoản không hợp lệ"
        )
    return await _build_profile(db, refreshed)
