import asyncio
import ipaddress
import logging
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core import security
from app.core.config import settings
from app.core.csrf import new_csrf_token
from app.core.ratelimit import rate_limit
from app.crud import user as user_crud
from app.db.session import get_db
from app.models.auth import User, UserIdentity
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    TokenPair,
    UserSummary,
)
from app.services import oauth

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger("app.performance")


def _client_ip(request: Request) -> str | None:
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
            full_name=user.profile.full_name if user.profile else None,
        ),
    )


async def _issue_tokens(
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
        ip_address=_client_ip(request),
    )
    await user_crud.touch_last_login(db, user)
    return _token_pair(user, access, refresh)


def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    secure = settings.cookie_secure_resolved
    # 2a hybrid: access memory + httpOnly fallback, cả 2 cookie path=/ để middleware thấy
    response.set_cookie(
        key="access_token",
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
        key="refresh_token",
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
        key="csrf_token",
        value=csrf,
        httponly=False,
        secure=secure,
        samesite=settings.cookie_samesite,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/",
        domain=settings.cookie_domain,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key="access_token", path="/", domain=settings.cookie_domain)
    response.delete_cookie(key="refresh_token", path="/api/auth", domain=settings.cookie_domain)
    response.delete_cookie(key="refresh_token", path="/", domain=settings.cookie_domain)
    response.delete_cookie(key="csrf_token", path="/", domain=settings.cookie_domain)


# ---------------------------------------------------------------------------
# Microsoft 365 / Outlook OAuth
# ---------------------------------------------------------------------------
_OAUTH_TX_COOKIE = "oauth_tx"
_OAUTH_TX_PATH = "/api/auth/oauth"
_OAUTH_TX_MAX_AGE = 600


def _clear_oauth_tx_cookie(response: Response) -> None:
    response.delete_cookie(
        key=_OAUTH_TX_COOKIE,
        path=_OAUTH_TX_PATH,
        domain=settings.cookie_domain,
    )


def _oauth_error_redirect(code: str) -> RedirectResponse:
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
        "exp": datetime.now(timezone.utc) + timedelta(seconds=_OAUTH_TX_MAX_AGE),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    response.set_cookie(
        key=_OAUTH_TX_COOKIE,
        value=token,
        httponly=True,
        secure=settings.cookie_secure_resolved,
        samesite=settings.cookie_samesite,
        max_age=_OAUTH_TX_MAX_AGE,
        path=_OAUTH_TX_PATH,
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
            select(UserIdentity).where(
                UserIdentity.provider == "microsoft",
                UserIdentity.provider_user_id == profile.provider_user_id,
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
                select(UserIdentity).where(
                    UserIdentity.user_id == user.id,
                    UserIdentity.provider == "microsoft",
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
                UserIdentity(
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
            UserIdentity(
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


@router.get(
    "/oauth/microsoft/start",
    dependencies=[Depends(rate_limit(10, 60, "oauth_start"))],
)
async def microsoft_start(
    next_path: str | None = Query(default=None, alias="next"),
):
    """Bắt đầu đăng nhập Microsoft 365 (Outlook)."""
    if not settings.microsoft_oauth_enabled:
        return _oauth_error_redirect("not_configured")
    tx = oauth.new_transaction(next_path)
    response = RedirectResponse(
        oauth.build_authorize_url(tx), status_code=status.HTTP_302_FOUND
    )
    _set_oauth_tx_cookie(response, tx)
    return response


@router.get(
    "/oauth/microsoft/callback",
    dependencies=[Depends(rate_limit(20, 60, "oauth_callback"))],
)
async def microsoft_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Nhận callback từ Microsoft, đăng nhập hoặc tạo tài khoản sinh viên."""
    raw_tx = request.cookies.get(_OAUTH_TX_COOKIE)
    if not raw_tx:
        return _oauth_error_redirect("state_invalid")
    try:
        tx = _decode_oauth_tx(raw_tx)
    except Exception:  # noqa: BLE001 — cookie hỏng/hết hạn
        return _oauth_error_redirect("state_invalid")

    if not state or state != tx.get("state"):
        return _oauth_error_redirect("state_invalid")
    if error:
        return _oauth_error_redirect(
            "access_denied" if error == "access_denied" else "oauth_failed"
        )
    if not code:
        return _oauth_error_redirect("oauth_failed")

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
        pair = await _issue_tokens(db, user, request)
        await db.commit()
    except oauth.OAuthError as exc:
        await db.rollback()
        logger.warning("microsoft oauth failed: %s", exc.code)
        return _oauth_error_redirect(exc.code)
    except Exception:  # noqa: BLE001 — không lộ chi tiết lỗi ra ngoài
        await db.rollback()
        logger.exception("microsoft oauth unexpected error")
        return _oauth_error_redirect("server_error")

    response = RedirectResponse(
        f"{settings.frontend_url.rstrip('/')}{_safe_next(tx.get('next'), user)}",
        status_code=status.HTTP_302_FOUND,
    )
    _set_auth_cookies(response, pair.access_token, pair.refresh_token)
    _clear_oauth_tx_cookie(response)
    return response


@router.post(
    "/register",
    status_code=status.HTTP_403_FORBIDDEN,
    dependencies=[Depends(rate_limit(5, 60, "register"))],
)
async def register():
    """Đăng ký bằng email/mật khẩu đã bị tắt.

    Tài khoản mật khẩu chỉ tồn tại từ seed development. Mọi tài khoản mới
    phải được tạo qua Microsoft 365 (Outlook).
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Đăng ký bằng mật khẩu đã bị tắt. Vui lòng đăng nhập bằng Outlook.",
    )


@router.post(
    "/login",
    response_model=TokenPair,
    dependencies=[Depends(rate_limit(10, 60, "login"))],
)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    started = time.perf_counter()
    user = await user_crud.get_user_by_email(db, body.email)
    lookup_ms = (time.perf_counter() - started) * 1000
    password_started = time.perf_counter()
    password_valid = bool(
        user
        and user.deleted_at is None
        and user.status == "active"
        and await asyncio.to_thread(
            security.verify_password, body.password, user.password_hash
        )
    )
    password_ms = (time.perf_counter() - password_started) * 1000
    if (
        user is None
        or user.deleted_at is not None
        or user.status != "active"
        or not password_valid
    ):
        logger.info(
            "login result=denied lookup_ms=%.1f password_ms=%.1f total_ms=%.1f",
            lookup_ms,
            password_ms,
            (time.perf_counter() - started) * 1000,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng",
        )
    pair = await _issue_tokens(db, user, request)
    await db.commit()
    commit_ms = (time.perf_counter() - password_started) * 1000 - password_ms
    _set_auth_cookies(response, pair.access_token, pair.refresh_token)
    response.headers["Server-Timing"] = (
        f"auth_db;dur={lookup_ms:.1f}, password;dur={password_ms:.1f}, "
        f"session;dur={commit_ms:.1f}"
    )
    logger.info(
        "login result=success lookup_ms=%.1f password_ms=%.1f session_ms=%.1f total_ms=%.1f",
        lookup_ms,
        password_ms,
        commit_ms,
        (time.perf_counter() - started) * 1000,
    )
    return pair


@router.post("/refresh", response_model=TokenPair, dependencies=[Depends(rate_limit(20, 60, "refresh"))])
async def refresh(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    # 2a hybrid: ưu tiên cookie httpOnly, fallback body để tương thích
    raw_refresh = None
    if body and body.refresh_token:
        raw_refresh = body.refresh_token
    else:
        raw_refresh = request.cookies.get("refresh_token")
    if not raw_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token không hợp lệ"
        )
    session = await user_crud.get_valid_session(
        db, security.hash_refresh_token(raw_refresh)
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token không hợp lệ"
        )
    user = await user_crud.get_user_by_id(db, session.user_id)
    if user is None or user.deleted_at is not None or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Tài khoản không hợp lệ"
        )
    await user_crud.revoke_session(db, session)
    pair = await _issue_tokens(db, user, request)
    await db.commit()
    _set_auth_cookies(response, pair.access_token, pair.refresh_token)
    return pair


@router.post(
    "/change-password",
    dependencies=[Depends(rate_limit(10, 60, "change-password"))],
)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Đổi mật khẩu tự nguyện.

    Đổi thành công sẽ thu hồi mọi refresh session khác, giữ lại phiên hiện tại.
    """
    # get_current_user có thể trả AuthUser từ cache; cần bản User gắn với DB
    # để đọc password_hash và ghi thay đổi.
    full_user = await user_crud.get_user_by_id(db, user.id)
    if full_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản không hợp lệ",
        )
    if not await asyncio.to_thread(
        security.verify_password, body.current_password, full_user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu hiện tại không đúng",
        )
    full_user.password_hash = await asyncio.to_thread(
        security.hash_password, body.new_password
    )
    raw_refresh = request.cookies.get("refresh_token")
    await user_crud.revoke_all_sessions(
        db,
        full_user.id,
        except_token_hash=(
            security.hash_refresh_token(raw_refresh) if raw_refresh else None
        ),
    )
    await db.commit()
    await user_crud.invalidate_auth_cache(full_user.id)
    return {"ok": True}


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    raw_refresh = None
    if body and body.refresh_token:
        raw_refresh = body.refresh_token
    else:
        raw_refresh = request.cookies.get("refresh_token")
    if raw_refresh:
        session = await user_crud.get_valid_session(
            db, security.hash_refresh_token(raw_refresh)
        )
        if session is not None:
            await user_crud.revoke_session(db, session)
            await db.commit()
    _clear_auth_cookies(response)
    return {"ok": True}
