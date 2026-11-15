"""Luồng xác thực dùng chung cho route auth.

Route `app/api/routes/auth.py` chỉ còn khai báo endpoint, dependency và response.
Các bước nghiệp vụ nằm ở đây: đăng nhập mật khẩu seed, phát cookie/token, xoay
vòng refresh token, đổi mật khẩu và Microsoft OAuth single-tenant.
"""

import asyncio
import ipaddress
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import jwt
from fastapi import HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import settings
from app.core.csrf import new_csrf_token
from app.crud import user as user_crud
from app.models.auth import OAuthAccount, User
from app.schemas.auth import RefreshRequest, TokenPair, UserSummary
from app.services import oauth

logger = logging.getLogger("app.performance")

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"

OAUTH_TX_COOKIE = "oauth_tx"
OAUTH_TX_PATH = "/api/auth/oauth"
OAUTH_TX_MAX_AGE = 600


# ---------------------------------------------------------------------------
# Cookie / token issuance
# ---------------------------------------------------------------------------


def client_ip(request: Request) -> str | None:
    host = request.client.host if request.client else None
    if not host:
        return None
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


# ---------------------------------------------------------------------------
# Microsoft 365 / Outlook OAuth
# ---------------------------------------------------------------------------


def _clear_oauth_tx_cookie(response: Response) -> None:
    response.delete_cookie(
        key=OAUTH_TX_COOKIE,
        path=OAUTH_TX_PATH,
        domain=settings.cookie_domain,
    )


def oauth_error_redirect(code: str) -> RedirectResponse:
    url = f"{settings.frontend_url.rstrip('/')}/account/login?oauthError={quote(code)}"
    response = RedirectResponse(url, status_code=status.HTTP_302_FOUND)
    _clear_oauth_tx_cookie(response)
    return response


def _set_oauth_tx_cookie(response: Response, tx: oauth.OAuthTransaction) -> None:
    payload = {
        "state": tx.state,
        "nonce": tx.nonce,
        "code_verifier": tx.code_verifier,
        "next": tx.next_path,
        "type": "oauth_tx",
        "exp": datetime.now(timezone.utc) + timedelta(seconds=OAUTH_TX_MAX_AGE),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    response.set_cookie(
        key=OAUTH_TX_COOKIE,
        value=token,
        httponly=True,
        secure=settings.cookie_secure_resolved,
        samesite=settings.cookie_samesite,
        max_age=OAUTH_TX_MAX_AGE,
        path=OAUTH_TX_PATH,
        domain=settings.cookie_domain,
    )


def _decode_oauth_tx(raw: str) -> dict:
    payload = jwt.decode(raw, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != "oauth_tx":
        raise ValueError("invalid oauth transaction")
    return payload


def _home_for(user: User) -> str:
    for code in ("teacher", "student", "admin"):
        if code in user.role_codes:
            return f"/{code}"
    return "/student"


def _safe_next(next_path: str | None, user: User) -> str:
    if next_path and ".." not in next_path and "\\" not in next_path:
        for code in user.role_codes:
            if next_path == f"/{code}" or next_path.startswith(f"/{code}/"):
                return next_path
    return _home_for(user)


async def _get_or_create_oauth_user(
    db: AsyncSession, profile: oauth.MicrosoftProfile
) -> User:
    identity = (
        await db.execute(
            select(OAuthAccount).where(
                OAuthAccount.provider == "microsoft",
                OAuthAccount.provider_user_id == profile.provider_user_id,
            )
        )
    ).scalar_one_or_none()
    if identity is not None:
        user = await user_crud.get_user_by_id(db, identity.user_id)
        if user is None or user.deleted_at is not None or user.status != "active":
            raise oauth.OAuthError("account_disabled")
        identity.email = profile.email
        identity.last_login_at = datetime.now(timezone.utc)
        return user

    user = await user_crud.get_user_by_email(db, profile.email)
    if user is not None:
        if user.deleted_at is not None or user.status != "active":
            raise oauth.OAuthError("account_disabled")
        existing_identity = (
            await db.execute(
                select(OAuthAccount).where(
                    OAuthAccount.user_id == user.id,
                    OAuthAccount.provider == "microsoft",
                )
            )
        ).scalar_one_or_none()
        if (
            existing_identity is not None
            and existing_identity.provider_user_id != profile.provider_user_id
        ):
            raise oauth.OAuthError("identity_conflict")
        if existing_identity is None:
            db.add(
                OAuthAccount(
                    user_id=user.id,
                    provider="microsoft",
                    provider_user_id=profile.provider_user_id,
                    email=profile.email,
                    last_login_at=datetime.now(timezone.utc),
                )
            )
        else:
            existing_identity.email = profile.email
            existing_identity.last_login_at = datetime.now(timezone.utc)
        return user

    try:
        user = await user_crud.create_student(
            db,
            email=profile.email,
            password_hash=None,
            full_name=profile.full_name,
        )
        db.add(
            OAuthAccount(
                user_id=user.id,
                provider="microsoft",
                provider_user_id=profile.provider_user_id,
                email=profile.email,
                last_login_at=datetime.now(timezone.utc),
            )
        )
        await db.flush()
    except IntegrityError:
        await db.rollback()
        user = await user_crud.get_user_by_email(db, profile.email)
        if user is None:
            raise oauth.OAuthError("server_error")

    # Đảm bảo roles/profile đã load trước khi phát token.
    loaded = await user_crud.get_user_by_id(db, user.id)
    if loaded is None:
        raise oauth.OAuthError("server_error")
    return loaded


def begin_microsoft_login(next_path: str | None) -> RedirectResponse:
    """Bắt đầu đăng nhập Microsoft 365 (Outlook)."""
    if not settings.microsoft_oauth_enabled:
        return oauth_error_redirect("not_configured")
    tx = oauth.new_transaction(next_path)
    response = RedirectResponse(
        oauth.build_authorize_url(tx), status_code=status.HTTP_302_FOUND
    )
    _set_oauth_tx_cookie(response, tx)
    return response


async def finish_microsoft_login(
    db: AsyncSession,
    request: Request,
    *,
    code: str | None,
    state: str | None,
    error: str | None,
) -> RedirectResponse:
    """Nhận callback từ Microsoft, đăng nhập hoặc tạo tài khoản sinh viên."""
    raw_tx = request.cookies.get(OAUTH_TX_COOKIE)
    if not raw_tx:
        return oauth_error_redirect("state_invalid")
    try:
        tx = _decode_oauth_tx(raw_tx)
    except Exception:  # noqa: BLE001 — cookie hỏng/hết hạn
        return oauth_error_redirect("state_invalid")

    if not state or state != tx.get("state"):
        return oauth_error_redirect("state_invalid")
    if error:
        return oauth_error_redirect(
            "access_denied" if error == "access_denied" else "oauth_failed"
        )
    if not code:
        return oauth_error_redirect("oauth_failed")

    try:
        tokens = await oauth.exchange_code(code, str(tx.get("code_verifier") or ""))
        id_token = tokens.get("id_token")
        if not id_token:
            raise oauth.OAuthError("token_invalid")
        claims = await asyncio.to_thread(
            oauth.validate_id_token, id_token, str(tx.get("nonce") or "")
        )
        profile = await oauth.resolve_profile(claims, tokens.get("access_token"))
        user = await _get_or_create_oauth_user(db, profile)
        pair = await issue_tokens(db, user, request)
        await db.commit()
    except oauth.OAuthError as exc:
        await db.rollback()
        logger.warning("microsoft oauth failed: %s", exc.code)
        return oauth_error_redirect(exc.code)
    except Exception:  # noqa: BLE001 — không lộ chi tiết lỗi ra ngoài
        await db.rollback()
        logger.exception("microsoft oauth unexpected error")
        return oauth_error_redirect("server_error")

    response = RedirectResponse(
        f"{settings.frontend_url.rstrip('/')}{_safe_next(tx.get('next'), user)}",
        status_code=status.HTTP_302_FOUND,
    )
    set_auth_cookies(response, pair.access_token, pair.refresh_token)
    _clear_oauth_tx_cookie(response)
    return response
