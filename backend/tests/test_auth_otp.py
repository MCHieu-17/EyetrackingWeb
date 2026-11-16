"""Đăng nhập sinh viên bằng email trường + OTP.

Các test dùng monkeypatch `send_otp_email` để không gửi SMTP thật.
Email sinh viên luôn dùng local-part 8 số duy nhất tại st.neu.edu.vn.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.crud import user as user_crud
from app.models.auth import User
from app.models.email_otp import EmailOtp
from app.models.profile import StudentProfile
from app.services import email_otp as email_otp_service
from tests.conftest import SessionLocal, create_user


def _capture_otp(monkeypatch) -> dict[str, str]:
    """Chặn SMTP, ghi lại email + mã OTP đã gửi."""
    sent: dict[str, str] = {}

    async def fake_send(email: str, code: str) -> None:
        sent["email"] = email
        sent["code"] = code

    monkeypatch.setattr(email_otp_service, "send_otp_email", fake_send)
    return sent


async def _new_student_identity() -> tuple[str, str]:
    """Sinh mã sinh viên 8 số chưa được dùng trong DB test."""
    for _ in range(50):
        local_part = f"{uuid.uuid4().int % 100_000_000:08d}"
        email = f"{local_part}@st.neu.edu.vn"
        async with SessionLocal() as db:
            existing_user = await user_crud.get_user_by_email(db, email)
            existing_code = (
                await db.execute(
                    select(StudentProfile.user_id).where(
                        StudentProfile.student_code == local_part
                    )
                )
            ).scalar_one_or_none()
        if existing_user is None and existing_code is None:
            return local_part, email
    raise AssertionError("không tìm được mã sinh viên trống")


async def _request_otp(client, email: str) -> dict:
    response = await client.post(
        "/api/auth/otp/request", json={"email": email}
    )
    assert response.status_code == 200, response.text
    assert response.headers.get("cache-control") == "no-store"
    return response.json()


async def _verify(client, challenge_id: str, code: str):
    return await client.post(
        "/api/auth/otp/verify",
        json={"challengeId": challenge_id, "code": code},
    )


def _error_code(response) -> str:
    detail = response.json()["detail"]
    assert isinstance(detail, dict)
    return detail["code"]


def _different_code(code: str) -> str:
    return "000000" if code != "000000" else "999999"


@pytest.mark.asyncio
async def test_request_otp_valid_email(client, monkeypatch):
    sent = _capture_otp(monkeypatch)
    _, email = await _new_student_identity()

    response = await client.post(
        "/api/auth/otp/request", json={"email": email}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["email"] == email
    assert body["challengeId"]
    assert body["delivery"] == "email"
    assert body["resendAfterSeconds"] == 60
    expires_at = datetime.fromisoformat(body["expiresAt"])
    assert expires_at > datetime.now(timezone.utc)
    assert sent["email"] == email
    assert len(sent["code"]) == 6 and sent["code"].isdigit()

    async with SessionLocal() as db:
        row = await db.get(EmailOtp, body["challengeId"])
    assert row is not None
    assert row.email == email
    assert row.attempts == 0
    assert row.consumed_at is None
    assert row.invalidated_at is None
    # Chỉ lưu HMAC, không lưu mã thô.
    assert row.code_hash != sent["code"]
    assert len(row.code_hash) == 64


@pytest.mark.asyncio
async def test_request_otp_rejects_domain_outside_school(client):
    response = await client.post(
        "/api/auth/otp/request", json={"email": "123456@gmail.com"}
    )

    assert response.status_code == 422, response.text
    assert _error_code(response) == "invalid_email"


@pytest.mark.asyncio
@pytest.mark.parametrize("local_part", ["123456", "1234567", "123456789", "abcdef"])
async def test_request_otp_rejects_non_eight_digit_student_id(client, local_part):
    response = await client.post(
        "/api/auth/otp/request",
        json={"email": f"{local_part}@st.neu.edu.vn"},
    )

    assert response.status_code == 422, response.text
    assert _error_code(response) == "invalid_email"


@pytest.mark.asyncio
async def test_request_otp_cooldown(client, monkeypatch):
    _capture_otp(monkeypatch)
    _, email = await _new_student_identity()
    await _request_otp(client, email)

    response = await client.post(
        "/api/auth/otp/request", json={"email": email}
    )

    assert response.status_code == 429, response.text
    assert _error_code(response) == "otp_cooldown"
    assert int(response.headers["retry-after"]) > 0


@pytest.mark.asyncio
async def test_verify_wrong_code_increments_attempts_and_locks(client, monkeypatch):
    sent = _capture_otp(monkeypatch)
    _, email = await _new_student_identity()
    challenge = await _request_otp(client, email)
    wrong = _different_code(sent["code"])

    for _ in range(4):
        response = await _verify(client, challenge["challengeId"], wrong)
        assert response.status_code == 400, response.text
        assert _error_code(response) == "otp_invalid"

    exhausted = await _verify(client, challenge["challengeId"], wrong)
    assert exhausted.status_code == 400, exhausted.text
    assert _error_code(exhausted) == "otp_too_many_attempts"

    # Mã đúng sau khi hết lượt vẫn bị từ chối vì challenge đã invalidated.
    replay = await _verify(
        client, challenge["challengeId"], sent["code"]
    )
    assert replay.status_code == 400, replay.text
    assert _error_code(replay) == "otp_consumed"

    async with SessionLocal() as db:
        row = await db.get(EmailOtp, challenge["challengeId"])
    assert row is not None
    assert row.attempts == 5
    assert row.invalidated_at is not None
    assert row.consumed_at is None


@pytest.mark.asyncio
async def test_verify_correct_code_creates_student_and_tokens(client, monkeypatch):
    sent = _capture_otp(monkeypatch)
    local_part, email = await _new_student_identity()
    challenge = await _request_otp(client, email)

    response = await _verify(
        client, challenge["challengeId"], sent["code"]
    )

    assert response.status_code == 200, response.text
    assert response.headers.get("cache-control") == "no-store"
    pair = response.json()
    assert pair["accessToken"]
    assert pair["refreshToken"]
    assert pair["user"]["email"] == email
    assert pair["user"]["roles"] == ["student"]
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies

    async with SessionLocal() as db:
        user = await user_crud.get_user_by_email(db, email)
        assert user is not None
        assert user.role == "student"
        assert user.status == "active"
        assert user.password_hash is None
        assert user.full_name == f"Sinh viên {local_part}"
        assert user.email_verified_at is not None
        profile = await db.get(StudentProfile, user.id)
        assert profile is not None
        assert profile.student_code == local_part

        otp = await db.get(EmailOtp, challenge["challengeId"])
        assert otp is not None and otp.consumed_at is not None

    profile_response = await client.get(
        "/api/me/profile",
        headers={"Authorization": f"Bearer {pair['accessToken']}"},
    )
    assert profile_response.status_code == 200, profile_response.text
    assert profile_response.json()["email"] == email


@pytest.mark.asyncio
async def test_verify_existing_user_keeps_role(client, monkeypatch):
    local_part = f"{uuid.uuid4().int % 100_000_000:08d}"
    email = f"{local_part}@st.neu.edu.vn"
    await create_user(email=email, role="teacher", full_name="Giáo viên NEU")
    sent = _capture_otp(monkeypatch)
    challenge = await _request_otp(client, email)

    response = await _verify(
        client, challenge["challengeId"], sent["code"]
    )

    assert response.status_code == 200, response.text
    pair = response.json()
    assert pair["user"]["roles"] == ["teacher"]
    async with SessionLocal() as db:
        user = await user_crud.get_user_by_email(db, email)
        assert user is not None
        assert user.role == "teacher"
        assert user.email_verified_at is not None
        assert await db.get(StudentProfile, user.id) is None


@pytest.mark.asyncio
async def test_verify_suspended_user_gets_403(client, monkeypatch):
    local_part = f"{uuid.uuid4().int % 100_000_000:08d}"
    email = f"{local_part}@st.neu.edu.vn"
    user_id = await create_user(email=email)
    async with SessionLocal() as db:
        user = await db.get(User, user_id)
        assert user is not None
        user.status = "suspended"
        await db.commit()

    sent = _capture_otp(monkeypatch)
    challenge = await _request_otp(client, email)

    response = await _verify(
        client, challenge["challengeId"], sent["code"]
    )

    assert response.status_code == 403, response.text
    assert _error_code(response) == "account_disabled"
    async with SessionLocal() as db:
        otp = await db.get(EmailOtp, challenge["challengeId"])
    assert otp is not None and otp.consumed_at is not None


@pytest.mark.asyncio
async def test_verify_expired_otp_rejected(client, monkeypatch):
    sent = _capture_otp(monkeypatch)
    _, email = await _new_student_identity()
    challenge = await _request_otp(client, email)
    async with SessionLocal() as db:
        row = await db.get(EmailOtp, challenge["challengeId"])
        assert row is not None
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.commit()

    response = await _verify(
        client, challenge["challengeId"], sent["code"]
    )

    assert response.status_code == 400, response.text
    assert _error_code(response) == "otp_expired"


@pytest.mark.asyncio
async def test_verify_consumed_otp_rejected_on_replay(client, monkeypatch):
    sent = _capture_otp(monkeypatch)
    _, email = await _new_student_identity()
    challenge = await _request_otp(client, email)
    first = await _verify(client, challenge["challengeId"], sent["code"])
    assert first.status_code == 200, first.text

    replay = await _verify(
        client, challenge["challengeId"], sent["code"]
    )

    assert replay.status_code == 400, replay.text
    assert _error_code(replay) == "otp_consumed"


@pytest.mark.asyncio
async def test_request_otp_without_smtp_returns_503(client):
    # conftest để SMTP_HOST rỗng và OTP_DEV_ECHO=false.
    _, email = await _new_student_identity()

    response = await client.post(
        "/api/auth/otp/request", json={"email": email}
    )

    assert response.status_code == 503, response.text
    assert _error_code(response) == "email_not_configured"
    async with SessionLocal() as db:
        row = (
            await db.execute(
                select(EmailOtp)
                .where(EmailOtp.email == email)
                .order_by(EmailOtp.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    assert row is not None
    assert row.invalidated_at is not None


@pytest.mark.asyncio
async def test_request_otp_when_smtp_refuses_returns_502(client, monkeypatch):
    async def refuse(_email: str, _code: str) -> None:
        raise email_otp_service.EmailDeliveryError("550 5.4.1")

    monkeypatch.setattr(email_otp_service, "send_otp_email", refuse)
    _, email = await _new_student_identity()

    response = await client.post(
        "/api/auth/otp/request", json={"email": email}
    )

    assert response.status_code == 502, response.text
    assert _error_code(response) == "email_send_failed"


@pytest.mark.asyncio
async def test_request_otp_dev_echo_falls_back_when_smtp_fails(
    client, monkeypatch
):
    async def refuse(_email: str, _code: str) -> None:
        raise email_otp_service.EmailDeliveryError("temporary SMTP error")

    monkeypatch.setattr(email_otp_service, "send_otp_email", refuse)
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "otp_dev_echo", True)
    _, email = await _new_student_identity()

    response = await client.post(
        "/api/auth/otp/request", json={"email": email}
    )

    assert response.status_code == 200, response.text
    assert response.json()["delivery"] == "dev"
