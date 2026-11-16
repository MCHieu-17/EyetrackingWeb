"""Đăng nhập sinh viên bằng email trường + OTP.

Luồng:
1. `request_email_otp`: chuẩn hoá email, giới hạn tần suất, vô hiệu challenge
   cũ, sinh mã 6 số, lưu HMAC rồi gửi SMTP.
2. `verify_email_otp`: khoá row OTP, so HMAC, tạo/tìm user, đánh dấu
   `users.email_verified_at` và trả user để route phát token.

Mã OTP không bao giờ được log ở production; chỉ log khi DEBUG + OTP_DEV_ECHO.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import math
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import Request
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.ratelimit import enforce_rate_limit, real_client_ip
from app.crud import user as user_crud
from app.models.auth import User
from app.models.email_otp import EmailOtp
from app.models.profile import StudentProfile
from app.services.auth_flow import client_ip
from app.services.mailer import (
    EmailDeliveryError,
    EmailDeliveryNotConfigured,
    send_otp_email,
)

logger = logging.getLogger("app.auth.otp")

EMAIL_MAX_LENGTH = 255
STUDENT_CODE_MAX_LENGTH = 30


# ---------------------------------------------------------------------------
# Lỗi typed cho route map sang HTTP
# ---------------------------------------------------------------------------


class EmailOtpError(Exception):
    """Lỗi OTP có mã ổn định (`code`) để route chọn HTTP status phù hợp."""

    code = "otp_error"
    default_message = "Không thể xác thực mã OTP."

    def __init__(
        self,
        message: str | None = None,
        *,
        retry_after_seconds: int | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.retry_after_seconds = retry_after_seconds
        super().__init__(self.message)


class InvalidStudentEmailError(EmailOtpError):
    code = "invalid_email"
    default_message = "Email không hợp lệ. Vui lòng dùng email sinh viên NEU."


class OtpCooldownError(EmailOtpError):
    code = "otp_cooldown"
    default_message = "Vui lòng chờ trước khi yêu cầu mã xác nhận mới."


class OtpInvalidError(EmailOtpError):
    code = "otp_invalid"
    default_message = "Mã xác nhận không đúng. Vui lòng kiểm tra lại."


class OtpExpiredError(EmailOtpError):
    code = "otp_expired"
    default_message = "Mã xác nhận đã hết hạn. Vui lòng yêu cầu mã mới."


class OtpConsumedError(EmailOtpError):
    code = "otp_consumed"
    default_message = (
        "Mã xác nhận đã được sử dụng hoặc không còn hiệu lực. "
        "Vui lòng yêu cầu mã mới."
    )


class OtpTooManyAttemptsError(EmailOtpError):
    code = "otp_too_many_attempts"
    default_message = (
        "Bạn đã nhập sai quá số lần cho phép. Vui lòng yêu cầu mã mới."
    )


class AccountDisabledError(EmailOtpError):
    code = "account_disabled"
    default_message = "Tài khoản không còn hoạt động. Vui lòng liên hệ quản trị viên."


class EmailNotConfiguredError(EmailOtpError):
    code = "email_not_configured"
    default_message = (
        "Hệ thống chưa cấu hình gửi email xác nhận. Vui lòng thử lại sau."
    )


class EmailSendFailedError(EmailOtpError):
    code = "email_send_failed"
    default_message = "Không gửi được email xác nhận. Vui lòng thử lại sau."


class OtpConfigError(EmailOtpError):
    code = "otp_config_error"
    default_message = "Cấu hình xác thực email chưa hợp lệ. Vui lòng liên hệ quản trị viên."


class OtpConflictError(EmailOtpError):
    code = "otp_conflict"
    default_message = "Không thể hoàn tất đăng nhập. Vui lòng thử lại."


# ---------------------------------------------------------------------------
# Tiện ích
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OtpChallenge:
    challenge_id: str
    email: str
    expires_at: datetime
    resend_after_seconds: int
    delivery: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:2]}{'*' * max(0, len(local) - 2)}@{domain}"


def _invalid_email_message() -> str:
    domains = ", ".join(settings.otp_allowed_domain_list)
    if domains:
        return (
            "Email không hợp lệ. Vui lòng dùng email trường "
            f"({domains}) với mã sinh viên đúng định dạng."
        )
    return "Email không hợp lệ. Vui lòng dùng email trường của bạn."


def normalize_student_email(email: str) -> str:
    """Chuẩn hoá + kiểm tra domain trường và phần local (mã sinh viên)."""
    normalized = (email or "").strip().lower()
    if (
        not normalized
        or len(normalized) > EMAIL_MAX_LENGTH
        or normalized.count("@") != 1
        or any(char.isspace() for char in normalized)
    ):
        raise InvalidStudentEmailError(_invalid_email_message())

    local_part, domain = normalized.rsplit("@", 1)
    if not local_part or domain not in settings.otp_allowed_domain_list:
        raise InvalidStudentEmailError(_invalid_email_message())

    try:
        matched = re.fullmatch(settings.otp_student_id_pattern, local_part)
    except re.error as exc:
        logger.error("OTP_STUDENT_ID_PATTERN không phải regex hợp lệ")
        raise OtpConfigError() from exc
    if matched is None:
        raise InvalidStudentEmailError(_invalid_email_message())
    return normalized


def _hash_code(email: str, code: str) -> str:
    """HMAC-SHA256 của `email:code`; không lưu mã thô trong DB."""
    secret = settings.otp_hash_secret_resolved.encode("utf-8")
    payload = f"{email}:{code}".encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


async def _lock_email(db: AsyncSession, email: str) -> None:
    """Khoá advisory theo email để hai challenge không tạo trùng user."""
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:email, 0))"),
        {"email": email},
    )


async def _ensure_student_profile(
    db: AsyncSession, user: User, local_part: str
) -> None:
    """Tạo student_profile nếu chưa có và mã sinh viên chưa bị dùng."""
    existing = (
        await db.execute(
            select(StudentProfile.user_id).where(
                StudentProfile.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return

    if len(local_part) > STUDENT_CODE_MAX_LENGTH:
        logger.warning(
            "bỏ qua student_profile vì mã sinh viên quá dài user=%s", user.id
        )
        return

    code_owner = (
        await db.execute(
            select(StudentProfile.user_id).where(
                StudentProfile.student_code == local_part
            )
        )
    ).scalar_one_or_none()
    if code_owner is not None:
        logger.warning(
            "mã sinh viên đã được dùng, bỏ qua student_profile user=%s", user.id
        )
        return

    # Savepoint: race hiếm gặp trên unique(student_code) không làm hỏng
    # transaction đăng nhập (OTP vẫn được consume bình thường).
    try:
        async with db.begin_nested():
            db.add(StudentProfile(user_id=user.id, student_code=local_part))
            await db.flush()
    except IntegrityError:
        logger.warning(
            "mã sinh viên vừa được dùng, bỏ qua student_profile user=%s", user.id
        )


# ---------------------------------------------------------------------------
# Phát hành OTP
# ---------------------------------------------------------------------------


async def request_email_otp(
    db: AsyncSession, email: str, request: Request
) -> OtpChallenge:
    normalized = normalize_student_email(email)

    # Kiểm tra cooldown TRƯỚC khi tiêu thụ quota theo giờ. Người dùng bấm gửi
    # lại trong 60 giây không được tính là một lượt mới, nếu không vài lần bấm
    # nhầm sẽ khoá email cả giờ dù chưa có mã nào được gửi thành công.
    now = _utc_now()
    latest_created = (
        await db.execute(
            select(EmailOtp.created_at)
            .where(EmailOtp.email == normalized)
            .order_by(EmailOtp.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest_created is not None:
        elapsed = (now - _as_utc(latest_created)).total_seconds()
        if elapsed < settings.otp_resend_seconds:
            retry_after = max(1, math.ceil(settings.otp_resend_seconds - elapsed))
            raise OtpCooldownError(
                f"Vui lòng chờ {retry_after} giây trước khi yêu cầu mã mới.",
                retry_after_seconds=retry_after,
            )

    # Giới hạn theo email (hash để không lưu email thô trong Redis key).
    email_digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    await enforce_rate_limit(
        f"otp:email:{email_digest}",
        settings.otp_max_per_email_per_hour,
        3600,
        detail=(
            "Email này đã yêu cầu quá nhiều mã OTP trong một giờ. "
            "Vui lòng thử lại sau."
        ),
    )
    ip_address = client_ip(request)
    await enforce_rate_limit(
        f"otp:ip:{real_client_ip(request)}",
        settings.otp_max_per_ip_per_hour,
        3600,
        detail="Bạn đã yêu cầu quá nhiều mã OTP. Vui lòng thử lại sau.",
    )

    # Chỉ một challenge hoạt động / email: vô hiệu các row cũ trước khi insert.
    await db.execute(
        update(EmailOtp)
        .where(
            EmailOtp.email == normalized,
            EmailOtp.consumed_at.is_(None),
            EmailOtp.invalidated_at.is_(None),
        )
        .values(invalidated_at=now)
    )

    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge = EmailOtp(
        email=normalized,
        code_hash=_hash_code(normalized, code),
        expires_at=now + timedelta(seconds=settings.otp_ttl_seconds),
        attempts=0,
        max_attempts=settings.otp_max_attempts,
        requested_ip=ip_address,
    )
    db.add(challenge)
    try:
        await db.flush()
        await db.commit()
    except IntegrityError as exc:
        # Hai request đồng thời cùng email: request sau nhận cooldown.
        await db.rollback()
        raise OtpCooldownError(
            "Vui lòng chờ trước khi yêu cầu mã xác nhận mới.",
            retry_after_seconds=settings.otp_resend_seconds,
        ) from exc

    delivery = "email"
    try:
        await send_otp_email(normalized, code)
    except EmailDeliveryNotConfigured as exc:
        if settings.debug and settings.otp_dev_echo:
            logger.warning(
                "SMTP chưa cấu hình; OTP dev cho %s là %s (chỉ log ở DEBUG)",
                _mask_email(normalized),
                code,
            )
            delivery = "dev"
        else:
            challenge.invalidated_at = _utc_now()
            await db.commit()
            raise EmailNotConfiguredError() from exc
    except EmailDeliveryError as exc:
        # Cùng fallback dev như trường hợp chưa cấu hình SMTP: khi đang phát
        # triển local, một lỗi SMTP tạm thời không nên chặn hoàn toàn đăng nhập.
        if settings.debug and settings.otp_dev_echo:
            logger.warning(
                "SMTP lỗi; OTP dev cho %s là %s (chỉ log ở DEBUG)",
                _mask_email(normalized),
                code,
            )
            delivery = "dev"
        else:
            challenge.invalidated_at = _utc_now()
            await db.commit()
            raise EmailSendFailedError() from exc

    return OtpChallenge(
        challenge_id=str(challenge.id),
        email=normalized,
        expires_at=challenge.expires_at,
        resend_after_seconds=settings.otp_resend_seconds,
        delivery=delivery,
    )


# ---------------------------------------------------------------------------
# Xác thực OTP
# ---------------------------------------------------------------------------


async def verify_email_otp(
    db: AsyncSession, challenge_id: str, code: str
) -> User:
    try:
        parsed_id = UUID(str(challenge_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise OtpInvalidError() from exc

    challenge = (
        await db.execute(
            select(EmailOtp)
            .where(EmailOtp.id == str(parsed_id))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if challenge is None:
        raise OtpInvalidError()

    now = _utc_now()
    if challenge.consumed_at is not None or challenge.invalidated_at is not None:
        raise OtpConsumedError()
    if _as_utc(challenge.expires_at) <= now:
        raise OtpExpiredError()
    if challenge.attempts >= challenge.max_attempts:
        raise OtpTooManyAttemptsError()

    if not hmac.compare_digest(_hash_code(challenge.email, code), challenge.code_hash):
        challenge.attempts += 1
        exhausted = challenge.attempts >= challenge.max_attempts
        if exhausted:
            challenge.invalidated_at = now
        await db.commit()
        if exhausted:
            raise OtpTooManyAttemptsError()
        raise OtpInvalidError()

    # Mã đúng: consume trước khi tạo/tìm user để không thể dùng lại.
    challenge.consumed_at = now
    await _lock_email(db, challenge.email)

    local_part = challenge.email.split("@", 1)[0]
    user = await user_crud.get_user_by_email(db, challenge.email)
    if user is not None:
        if user.deleted_at is not None or user.status != "active":
            await db.commit()
            raise AccountDisabledError()
    else:
        try:
            user = await user_crud.create_student(
                db,
                email=challenge.email,
                password_hash=None,
                full_name=f"Sinh viên {local_part}",
            )
        except IntegrityError as exc:
            # Hiếm: user được tạo bởi tiến trình khác dù đã khoá advisory.
            await db.rollback()
            raise OtpConflictError() from exc

    if user.role == "student":
        await _ensure_student_profile(db, user, local_part)

    user.email_verified_at = now
    await db.commit()
    return user
