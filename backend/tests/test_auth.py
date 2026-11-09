import uuid

import pytest

from tests.conftest import create_user


@pytest.mark.asyncio
async def test_login_refresh_logout(client):
    email = f"auth-{uuid.uuid4().hex[:8]}@example.com"
    await create_user(email=email)

    response = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert response.status_code == 200, response.text
    pair = response.json()
    assert pair["accessToken"]
    assert pair["refreshToken"]
    assert pair["user"]["email"] == email

    refresh = await client.post(
        "/api/auth/refresh",
        json={"refreshToken": pair["refreshToken"]},
    )
    assert refresh.status_code == 200, refresh.text
    assert refresh.json()["accessToken"]

    profile = await client.get(
        "/api/me/profile",
        headers={"Authorization": f"Bearer {pair['accessToken']}"},
    )
    assert profile.status_code == 200, profile.text
    assert profile.json()["email"] == email

    logout = await client.post("/api/auth/logout")
    assert logout.status_code == 200


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    email = f"auth-bad-{uuid.uuid4().hex[:8]}@example.com"
    await create_user(email=email)

    response = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "WrongPassword123!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_profile_requires_auth(client):
    response = await client.get("/api/me/profile")
    assert response.status_code == 401
