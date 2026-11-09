"""Smoke test cho metrics nội bộ dùng khi load test."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_internal_metrics(client):
    response = await client.get("/internal/metrics")
    assert response.status_code == 200, response.text
    data = response.json()
    assert "db_pool" in data
    assert "queues" in data
    assert "redis" in data
    assert data["db_pool"]["size"] >= 0
