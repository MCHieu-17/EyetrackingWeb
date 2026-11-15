from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.profile import StudentProfile, TeacherProfile


async def upsert_user_profile(
    db: AsyncSession,
    *,
    user_id: str,
    full_name: str,
    date_of_birth: date | None,
    gender: str | None,
    phone: str | None,
    avatar_url: str | None,
) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise LookupError("user not found")
    user.full_name = full_name
    user.date_of_birth = date_of_birth
    user.gender = gender
    user.phone = phone
    user.avatar_url = avatar_url
    return user


async def get_student_profile(db: AsyncSession, user_id: str) -> StudentProfile | None:
    stmt = select(StudentProfile).where(StudentProfile.user_id == user_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_teacher_profile(db: AsyncSession, user_id: str) -> TeacherProfile | None:
    stmt = select(TeacherProfile).where(TeacherProfile.user_id == user_id)
    return (await db.execute(stmt)).scalar_one_or_none()
