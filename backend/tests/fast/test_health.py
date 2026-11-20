"""Hợp đồng tối thiểu: health, config, auth bắt buộc."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.fast


async def test_health_public(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["schemaGeneration"] == "13"
    assert body["dbInstanceId"]


async def test_api_health_alias(client: AsyncClient):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_runtime_config_contract(client: AsyncClient):
    response = await client.get("/api/config")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert set(body) == {"gazeFps", "maxUploadBytes", "maxSlidePages"}
    assert all(isinstance(value, int) for value in body.values())
    assert 1 <= body["gazeFps"] <= 60


async def test_private_endpoint_requires_auth(client: AsyncClient):
    response = await client.get("/api/me/profile")
    assert response.status_code == 401
    assert response.json()["detail"] == "Chưa đăng nhập"
