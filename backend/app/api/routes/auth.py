import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.models.auth import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    OtpRequestIn,
    OtpRequestOut,
    OtpVerifyIn,
    RefreshRequest,
    TokenPair,
)
from app.services import auth_flow, email_otp

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger("app.performance")

# Mã lỗi typed của email OTP → HTTP status cho client.
_OTP_ERROR_STATUS: dict[str, int] = {
    "invalid_email": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "otp_cooldown": status.HTTP_429_TOO_MANY_REQUESTS,
    "otp_invalid": status.HTTP_400_BAD_REQUEST,
    "otp_expired": status.HTTP_400_BAD_REQUEST,
    "otp_consumed": status.HTTP_400_BAD_REQUEST,
    "otp_too_many_attempts": status.HTTP_400_BAD_REQUEST,
    "account_disabled": status.HTTP_403_FORBIDDEN,
    "email_not_configured": status.HTTP_503_SERVICE_UNAVAILABLE,
    "email_send_failed": status.HTTP_502_BAD_GATEWAY,
    "otp_config_error": status.HTTP_503_SERVICE_UNAVAILABLE,
    "otp_conflict": status.HTTP_409_CONFLICT,
}


def _otp_http_exception(exc: email_otp.EmailOtpError) -> HTTPException:
    """Map lỗi OTP sang HTTP kèm `{code, message}` và Retry-After khi có."""
    headers = {"Cache-Control": "no-store"}
    if exc.retry_after_seconds:
        headers["Retry-After"] = str(exc.retry_after_seconds)
    return HTTPException(
        status_code=_OTP_ERROR_STATUS.get(
            exc.code, status.HTTP_400_BAD_REQUEST
        ),
        detail={"code": exc.code, "message": exc.message},
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Đăng nhập sinh viên bằng email trường + OTP
# ---------------------------------------------------------------------------


@router.post(
    "/otp/request",
    response_model=OtpRequestOut,
    dependencies=[Depends(rate_limit(5, 60, "otp_request"))],
)
async def request_otp(
    body: OtpRequestIn,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Gửi mã OTP 6 số tới email sinh viên NEU."""
    response.headers["Cache-Control"] = "no-store"
    try:
        challenge = await email_otp.request_email_otp(
            db, str(body.email), request
        )
    except email_otp.EmailOtpError as exc:
        raise _otp_http_exception(exc) from exc
    return OtpRequestOut(
        challenge_id=challenge.challenge_id,
        email=challenge.email,
        expires_at=challenge.expires_at,
        resend_after_seconds=challenge.resend_after_seconds,
        delivery=challenge.delivery,
    )


@router.post(
    "/otp/verify",
    response_model=TokenPair,
    dependencies=[Depends(rate_limit(10, 60, "otp_verify"))],
)
async def verify_otp(
    body: OtpVerifyIn,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Xác nhận OTP, tạo tài khoản sinh viên nếu cần và phát token/cookie."""
    response.headers["Cache-Control"] = "no-store"
    try:
        user = await email_otp.verify_email_otp(
            db, body.challenge_id, body.code
        )
    except email_otp.EmailOtpError as exc:
        raise _otp_http_exception(exc) from exc

    pair = await auth_flow.issue_tokens(db, user, request)
    await db.commit()
    auth_flow.set_auth_cookies(
        response, pair.access_token, pair.refresh_token
    )
    return pair


@router.post(
    "/register",
    status_code=status.HTTP_403_FORBIDDEN,
    dependencies=[Depends(rate_limit(5, 60, "register"))],
)
async def register():
    """Đăng ký bằng email/mật khẩu đã bị tắt.

    Tài khoản mật khẩu chỉ tồn tại từ seed development. Tài khoản mới được
    tạo tự động khi sinh viên xác thực OTP email trường.
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Đăng ký bằng mật khẩu đã bị tắt. "
            "Vui lòng đăng nhập bằng email sinh viên và mã OTP."
        ),
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
