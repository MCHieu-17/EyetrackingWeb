from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import enforce_rate_limit
from app.core.security import decode_access_token
from app.crud.user import get_user_for_auth_cached
from app.db.session import get_db
from app.models.auth import User

oauth2_scheme = HTTPBearer(auto_error=False)


async def _authenticate(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
) -> User:
    # 2a: ưu tiên Authorization header (memory token), fallback httpOnly cookie access_token
    # Nếu auth qua cookie cho state-changing thì verify CSRF
    raw_token: str | None = None
    via_cookie = False
    if credentials is not None:
        raw_token = credentials.credentials
    else:
        raw_token = request.cookies.get("access_token")
        via_cookie = raw_token is not None
    if raw_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập"
        )
    if via_cookie and request.method.upper() in ("POST", "PATCH", "PUT", "DELETE"):
        from app.core.csrf import verify_csrf

        verify_csrf(request)
    try:
        payload = decode_access_token(raw_token)
    except PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token không hợp lệ"
        )
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token không hợp lệ"
        )
    user = await get_user_for_auth_cached(db, payload["sub"])
    if user is None or user.deleted_at is not None or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Tài khoản không hợp lệ"
        )
    return user


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    # Không còn bắt buộc đổi mật khẩu ở lần đăng nhập đầu. Người dùng vẫn có
    # thể tự đổi mật khẩu qua /account/change-password nếu muốn.
    return await _authenticate(request, credentials, db)


def require_roles(*roles: str):
    async def checker(user: User = Depends(get_current_user)) -> User:
        if not set(roles) & set(user.role_codes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền"
            )
        return user

    return checker


def user_rate_limit(
    limit: int,
    seconds: int,
    key_prefix: str,
    detail: str = "Quá nhiều yêu cầu.",
):
    """Dependency giới hạn tần suất theo tài khoản đang đăng nhập.

    Khác với `rate_limit` (theo IP), giới hạn này áp cho từng user trên mọi
    thiết bị/IP. Dùng cho các thao tác tốn tài nguyên như gửi tin nhắn chatbot.
    """

    async def dependency(user: User = Depends(get_current_user)):
        await enforce_rate_limit(
            f"{key_prefix}:user:{user.id}", limit, seconds, detail
        )

    return dependency


async def can_manage_course(db: AsyncSession, course, user: User) -> bool:
    """True nếu user là admin hoặc chủ khóa học (owner_id)."""
    if "admin" in user.role_codes:
        return True
    return getattr(course, "owner_id", None) == user.id


async def can_access_course(db: AsyncSession, course, user: User) -> bool:
    """True nếu user là admin, chủ khóa, hoặc giáo viên được phân công."""
    if await can_manage_course(db, course, user):
        return True
    if "teacher" not in user.role_codes:
        return False

    from app.models.course import CourseTeacher

    stmt = select(CourseTeacher.course_id).where(
        CourseTeacher.course_id == course.id,
        CourseTeacher.teacher_id == user.id,
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None
