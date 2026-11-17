"""Luồng xác thực dùng chung cho route auth.

Route `app/api/routes/auth.py` chỉ còn khai báo endpoint, dependency và response.
Các bước nghiệp vụ nằm ở đây: đăng nhập mật khẩu seed, phát cookie/token, xoay
vòng refresh token và đổi mật khẩu. Đăng nhập OTP email nằm ở
`app/services/email_otp.py`; gửi thư ở `app/services/mailer.py`.
"""

import asyncio
import ipaddress
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import settings
from app.core.csrf import new_csrf_token
from app.core.ratelimit import real_client_ip
from app.crud import user as user_crud
from app.models.auth import User
from app.schemas.auth import RefreshRequest, TokenPair, UserSummary

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"


# ---------------------------------------------------------------------------
# Cookie / token issuance
# ---------------------------------------------------------------------------


def client_ip(request: Request) -> str | None:
    """IP người dùng thật, đã đi qua proxy tin cậy nếu có.

    Trước đây chỉ đọc `request.client.host`, nên sau nginx/Cloudflare mọi
    audit log đều ghi IP container proxy.
    """
    host = real_client_ip(request)
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        return None


def _token_pair(user: User, access: str, refresh: str) -> TokenPair:
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        user=UserSummary(
            id=user.id,
            email=user.email,
            roles=user.role_codes,
            full_name=user.full_name or None,
        ),
    )


async def issue_tokens(
    db: AsyncSession, user: User, request: Request
) -> TokenPair:
    access = security.create_access_token(user.id, user.role_codes)
    refresh = security.new_refresh_token()
    await user_crud.create_session(
        db,
        user_id=user.id,
        refresh_token_hash=security.hash_refresh_token(refresh),
        expires_at=security.refresh_expiry(),
        user_agent=request.headers.get("user-agent"),
        ip_address=client_ip(request),
    )
    await user_crud.touch_last_login(db, user)
    return _token_pair(user, access, refresh)


def set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    secure = settings.cookie_secure_resolved
    # 2a hybrid: access memory + httpOnly fallback, cả 2 cookie path=/ để middleware thấy
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access,
        httponly=True,
        secure=secure,
        samesite=settings.cookie_samesite,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
        domain=settings.cookie_domain,
    )
    # refresh_token path=/ để middleware & mọi request đều thấy, vẫn httpOnly + SameSite bảo vệ
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh,
        httponly=True,
        secure=secure,
        samesite=settings.cookie_samesite,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/",
        domain=settings.cookie_domain,
    )
    # CSRF double-submit (non-httpOnly để JS đọc)
    csrf = new_csrf_token()
    response.set_cookie(
        key=CSRF_COOKIE,
        value=csrf,
        httponly=False,
        secure=secure,
        samesite=settings.cookie_samesite,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/",
        domain=settings.cookie_domain,
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key=ACCESS_COOKIE, path="/", domain=settings.cookie_domain)
    response.delete_cookie(
        key=REFRESH_COOKIE, path="/api/auth", domain=settings.cookie_domain
    )
    response.delete_cookie(key=REFRESH_COOKIE, path="/", domain=settings.cookie_domain)
    response.delete_cookie(key=CSRF_COOKIE, path="/", domain=settings.cookie_domain)


# ---------------------------------------------------------------------------
# Password login / refresh / logout / change password
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PasswordAuthResult:
    """Kết quả xác thực mật khẩu kèm thời gian cho log hiệu năng."""

    user: User | None
    lookup_ms: float
    password_ms: float


async def authenticate_password(
    db: AsyncSession, email: str, password: str
) -> PasswordAuthResult:
    """Xác thực tài khoản mật khẩu seed; trả user=None nếu bị từ chối."""
    started = time.perf_counter()
    user = await user_crud.get_user_by_email(db, email)
    lookup_ms = (time.perf_counter() - started) * 1000
    password_started = time.perf_counter()
    password_valid = bool(
        user
        and user.deleted_at is None
        and user.status == "active"
        and await asyncio.to_thread(
            security.verify_password, password, user.password_hash
        )
    )
    password_ms = (time.perf_counter() - password_started) * 1000
    if (
        user is None
        or user.deleted_at is not None
        or user.status != "active"
        or not password_valid
    ):
        return PasswordAuthResult(None, lookup_ms, password_ms)
    return PasswordAuthResult(user, lookup_ms, password_ms)


def refresh_token_value(
    body: RefreshRequest | None, request: Request
) -> str | None:
    """2a hybrid: ưu tiên body, fallback cookie httpOnly."""
    if body and body.refresh_token:
        return body.refresh_token
    return request.cookies.get(REFRESH_COOKIE)


async def rotate_refresh_token(
    db: AsyncSession, raw_refresh: str | None, request: Request
) -> TokenPair:
    """Thu hồi refresh session cũ và phát cặp token mới."""
    if not raw_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token không hợp lệ",
        )
    session = await user_crud.get_valid_session(
        db, security.hash_refresh_token(raw_refresh)
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token không hợp lệ",
        )
    user = await user_crud.get_user_by_id(db, session.user_id)
    if user is None or user.deleted_at is not None or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Tài khoản không hợp lệ"
        )
    await user_crud.revoke_session(db, session)
    pair = await issue_tokens(db, user, request)
    await db.commit()
    return pair


async def revoke_refresh_token(
    db: AsyncSession, raw_refresh: str | None
) -> None:
    if not raw_refresh:
        return
    session = await user_crud.get_valid_session(
        db, security.hash_refresh_token(raw_refresh)
    )
    if session is not None:
        await user_crud.revoke_session(db, session)
        await db.commit()


async def change_password(
    db: AsyncSession,
    user_id: str,
    current_password: str,
    new_password: str,
    raw_refresh: str | None,
) -> None:
    """Đổi mật khẩu và thu hồi mọi refresh session khác."""
    # get_current_user có thể trả AuthUser từ cache; cần bản User gắn với DB
    # để đọc password_hash và ghi thay đổi.
    full_user = await user_crud.get_user_by_id(db, user_id)
    if full_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản không hợp lệ",
        )
    if not await asyncio.to_thread(
        security.verify_password, current_password, full_user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu hiện tại không đúng",
        )
    full_user.password_hash = await asyncio.to_thread(
        security.hash_password, new_password
    )
    await user_crud.revoke_all_sessions(
        db,
        full_user.id,
        except_token_hash=(
            security.hash_refresh_token(raw_refresh) if raw_refresh else None
        ),
    )
    await db.commit()
    await user_crud.invalidate_auth_cache(full_user.id)
