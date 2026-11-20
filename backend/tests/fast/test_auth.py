"""Hợp đồng auth: password, cookie/CSRF, refresh rotation, OTP."""

from __future__ import annotations

import logging
import re

import pytest
from httpx import AsyncClient

from tests.conftest import PASSWORD, create_user, fetch_one

pytestmark = pytest.mark.fast


async def test_login_contract_and_cookies(client: AsyncClient):
    user = await create_user(role="teacher", email="teacher-login@example.com")
    response = await client.post(
        "/api/auth/login",
        json={"email": user["email"], "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tokenType"] == "bearer"
    assert body["accessToken"]
    assert body["refreshToken"]
    assert body["user"]["email"] == user["email"]
    assert body["user"]["roles"] == ["teacher"]

    cookies = {cookie.name: cookie for cookie in client.cookies.jar}
    assert {"access_token", "refresh_token", "csrf_token"} <= set(cookies)
    assert cookies["access_token"].has_nonstandard_attr("HttpOnly")
    assert cookies["refresh_token"].has_nonstandard_attr("HttpOnly")
    assert not cookies["csrf_token"].has_nonstandard_attr("HttpOnly")


async def test_login_rejects_wrong_password_and_unknown_email(client: AsyncClient):
    user = await create_user(email="denied@example.com")
    for email, password in ((user["email"], "WrongPassword123!"), ("nobody@example.com", PASSWORD)):
        response = await client.post(
            "/api/auth/login", json={"email": email, "password": password}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Email hoặc mật khẩu không đúng"


async def test_disabled_account_cannot_login(client: AsyncClient):
    user = await create_user(email="suspended@example.com", status="suspended")
    response = await client.post(
        "/api/auth/login", json={"email": user["email"], "password": PASSWORD}
    )
    assert response.status_code == 401


async def test_bearer_profile_and_cookie_csrf(client_factory):
    user = await create_user(email="profile@example.com")
    bearer = await client_factory()
    login = await bearer.post(
        "/api/auth/login", json={"email": user["email"], "password": PASSWORD}
    )
    bearer.headers["Authorization"] = f"Bearer {login.json()['accessToken']}"
    response = await bearer.get("/api/me/profile")
    assert response.status_code == 200
    assert response.json()["email"] == user["email"]

    cookie_client = await client_factory()
    await cookie_client.post(
        "/api/auth/login", json={"email": user["email"], "password": PASSWORD}
    )
    # Xoá Authorization để buộc đi qua cookie.
    cookie_client.headers.pop("Authorization", None)
    blocked = await cookie_client.patch(
        "/api/me/profile", json={"fullName": "Cookie User"}
    )
    assert blocked.status_code == 403

    csrf = cookie_client.cookies.get("csrf_token")
    assert csrf
    allowed = await cookie_client.patch(
        "/api/me/profile",
        json={"fullName": "Cookie User"},
        headers={"X-CSRF-Token": csrf},
    )
    assert allowed.status_code == 200
    assert allowed.json()["fullName"] == "Cookie User"


async def test_refresh_rotation_invalidates_old_token(client: AsyncClient):
    user = await create_user(email="refresh@example.com")
    login = await client.post(
        "/api/auth/login", json={"email": user["email"], "password": PASSWORD}
    )
    refresh = login.json()["refreshToken"]

    rotated = await client.post("/api/auth/refresh", json={"refreshToken": refresh})
    assert rotated.status_code == 200
    assert rotated.json()["refreshToken"] != refresh

    reused = await client.post("/api/auth/refresh", json={"refreshToken": refresh})
    assert reused.status_code == 401


async def test_logout_revokes_refresh(client: AsyncClient):
    user = await create_user(email="logout@example.com")
    login = await client.post(
        "/api/auth/login", json={"email": user["email"], "password": PASSWORD}
    )
    refresh = login.json()["refreshToken"]
    response = await client.post("/api/auth/logout", json={"refreshToken": refresh})
    assert response.status_code == 200
    assert (await client.post("/api/auth/refresh", json={"refreshToken": refresh})).status_code == 401


async def test_change_password_revokes_other_sessions(client_factory):
    user = await create_user(email="change@example.com")
    first = await client_factory()
    second = await client_factory()
    one = (
        await first.post(
            "/api/auth/login", json={"email": user["email"], "password": PASSWORD}
        )
    ).json()
    two = (
        await second.post(
            "/api/auth/login", json={"email": user["email"], "password": PASSWORD}
        )
    ).json()
    first.headers["Authorization"] = f"Bearer {one['accessToken']}"

    rejected = await first.post(
        "/api/auth/change-password",
        json={"currentPassword": "WrongPassword123!", "newPassword": "NewPassword123!"},
    )
    assert rejected.status_code == 400

    changed = await first.post(
        "/api/auth/change-password",
        json={"currentPassword": PASSWORD, "newPassword": "NewPassword123!"},
    )
    assert changed.status_code == 200

    old_other = await second.post(
        "/api/auth/refresh", json={"refreshToken": two["refreshToken"]}
    )
    assert old_other.status_code == 401
    # Phiên hiện tại vẫn dùng được.
    assert (await first.get("/api/me/profile")).status_code == 200

    new_login = await first.post(
        "/api/auth/login",
        json={"email": user["email"], "password": "NewPassword123!"},
    )
    assert new_login.status_code == 200


async def test_register_is_disabled(client: AsyncClient):
    response = await client.post(
        "/api/auth/register",
        json={"email": "new@example.com", "password": PASSWORD},
    )
    assert response.status_code == 403


async def test_otp_request_rejects_invalid_school_email(client: AsyncClient):
    response = await client.post(
        "/api/auth/otp/request", json={"email": "student@gmail.com"}
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_email"


async def _request_otp(client: AsyncClient, caplog, email: str) -> tuple[dict, str]:
    caplog.set_level(logging.WARNING, logger="app.services.email_otp")
    response = await client.post("/api/auth/otp/request", json={"email": email})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["delivery"] == "dev"
    match = re.search(r"là (\d{6})", caplog.text)
    assert match, caplog.text
    return body, match.group(1)


async def test_otp_happy_path_creates_student(client: AsyncClient, caplog):
    body, code = await _request_otp(client, caplog, "12345678@st.neu.edu.vn")
    assert body["resendAfterSeconds"] == 60

    verified = await client.post(
        "/api/auth/otp/verify",
        json={"challengeId": body["challengeId"], "code": code},
    )
    assert verified.status_code == 200, verified.text
    token = verified.json()
    assert token["user"]["roles"] == ["student"]
    row = await fetch_one(
        "SELECT u.email, u.email_verified_at, sp.student_code "
        "FROM users u JOIN student_profiles sp ON sp.user_id = u.id "
        "WHERE u.email = :email",
        {"email": "12345678@st.neu.edu.vn"},
    )
    assert row and row["student_code"] == "12345678"
    assert row["email_verified_at"] is not None


async def test_otp_cooldown_and_single_active_challenge(client: AsyncClient, caplog):
    first_body, _ = await _request_otp(client, caplog, "87654321@st.neu.edu.vn")
    second = await client.post(
        "/api/auth/otp/request", json={"email": "87654321@st.neu.edu.vn"}
    )
    assert second.status_code == 429
    assert int(second.headers["Retry-After"]) >= 1
    assert first_body["challengeId"]


async def test_otp_wrong_code_consumes_attempts(client: AsyncClient, caplog):
    body, _ = await _request_otp(client, caplog, "11112222@st.neu.edu.vn")
    for _ in range(4):
        response = await client.post(
            "/api/auth/otp/verify",
            json={"challengeId": body["challengeId"], "code": "000000"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "otp_invalid"
    fifth = await client.post(
        "/api/auth/otp/verify",
        json={"challengeId": body["challengeId"], "code": "000000"},
    )
    assert fifth.status_code == 400
    assert fifth.json()["detail"]["code"] == "otp_too_many_attempts"
    final = await client.post(
        "/api/auth/otp/verify",
        json={"challengeId": body["challengeId"], "code": "000000"},
    )
    assert final.status_code == 400
    assert final.json()["detail"]["code"] == "otp_consumed"
    row = await fetch_one(
        "SELECT attempts, invalidated_at FROM email_otps WHERE id = :id",
        {"id": body["challengeId"]},
    )
    assert row["attempts"] >= 5
    assert row["invalidated_at"] is not None


async def test_otp_expired_code(client: AsyncClient, caplog):
    body, code = await _request_otp(client, caplog, "33334444@st.neu.edu.vn")
    from tests.conftest import execute

    await execute(
        "UPDATE email_otps SET expires_at = now() - interval '1 second' "
        "WHERE id = :id",
        {"id": body["challengeId"]},
    )
    response = await client.post(
        "/api/auth/otp/verify",
        json={"challengeId": body["challengeId"], "code": code},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "otp_expired"
