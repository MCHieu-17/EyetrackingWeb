"""`GET /api/config` trả cấu hình runtime công khai cho frontend."""

from __future__ import annotations

import pytest

from app.core.config import settings


@pytest.mark.asyncio
async def test_runtime_config_returns_gaze_fps(client):
    response = await client.get("/api/config")

    assert response.status_code == 200
    assert response.json() == {
        "gazeFps": settings.gaze_fps,
        "maxUploadBytes": settings.max_upload_bytes,
        "maxSlidePages": settings.max_slide_pages,
    }
    assert "no-store" in response.headers["cache-control"]
