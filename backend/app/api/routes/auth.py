import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.models.auth import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    TokenPair,
)
from app.services import auth_flow

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger("app.performance")


# ---------------------------------------------------------------------------
# Microsoft 365 / Outlook OAuth
# ---------------------------------------------------------------------------


@router.get(
    "/oauth/microsoft/start",
    dependencies=[Depends(rate_limit(10, 60, "oauth_start"))],
)
async def microsoft_start(
    next_path: str | None = Query(default=None, alias="next"),
):
    """Bắt đầu đăng nhập Microsoft 365 (Outlook)."""
    return auth_flow.begin_microsoft_login(next_path)


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
    return await auth_flow.finish_microsoft_login(
        db, request, code=code, state=state, error=error
    )


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
    auth = await auth_flow.authenticate_password(db, body.email, body.password)
    lookup_ms = auth.lookup_ms
    password_ms = auth.password_ms
    if auth.user is None:
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
    session_started = time.perf_counter()
    pair = await auth_flow.issue_tokens(db, auth.user, request)
    await db.commit()
    commit_ms = (time.perf_counter() - session_started) * 1000
    auth_flow.set_auth_cookies(response, pair.access_token, pair.refresh_token)
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


@router.post(
    "/refresh",
    response_model=TokenPair,
    dependencies=[Depends(rate_limit(20, 60, "refresh"))],
)
async def refresh(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    raw_refresh = auth_flow.refresh_token_value(body, request)
    pair = await auth_flow.rotate_refresh_token(db, raw_refresh, request)
    auth_flow.set_auth_cookies(response, pair.access_token, pair.refresh_token)
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
    await auth_flow.change_password(
        db,
        user.id,
        body.current_password,
        body.new_password,
        request.cookies.get(auth_flow.REFRESH_COOKIE),
    )
    return {"ok": True}


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    raw_refresh = auth_flow.refresh_token_value(body, request)
    await auth_flow.revoke_refresh_token(db, raw_refresh)
    auth_flow.clear_auth_cookies(response)
    return {"ok": True}
