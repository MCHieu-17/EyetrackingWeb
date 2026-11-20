"""Smoke thật: MediaPipe + UniGaze trên một ảnh mặt mẫu."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import session as session_api
from app.main import app
from tests.conftest import frame

pytestmark = [pytest.mark.smoke, pytest.mark.gpu]


def test_model_smoke_on_sample_image():
    weights = session_api.settings.unigaze_weights_path()
    mediapipe = session_api.settings.mediapipe_weights_path()
    if not weights.is_file() or not mediapipe.is_file():
        pytest.skip(f"thiếu weights: {weights} / {mediapipe}")

    image = Path(__file__).resolve().parents[1] / "fixtures" / "face_sample.jpg"
    assert image.is_file()
    payload = image.read_bytes()

    with TestClient(app) as client:
        ready = client.get("/ready")
        assert ready.status_code == 200, ready.text
        assert ready.json()["pipeline_ready"] is True

        points = [
            {"id": "p00", "x": 0.2, "y": 0.3},
            {"id": "p10", "x": 0.8, "y": 0.3},
            {"id": "p01", "x": 0.2, "y": 0.7},
            {"id": "p11", "x": 0.8, "y": 0.7},
        ]
        created = client.post("/session", json={"points": points})
        assert created.status_code == 200
        sid = created.json()["session_id"]

        for point in points:
            response = client.post(
                f"/session/{sid}/calibrate",
                files={"image": ("face.jpg", payload, "image/jpeg")},
                data={"point_id": point["id"]},
            )
            assert response.status_code == 200, response.text
            assert response.json()["status"] == "accepted", response.text

        trained = client.post(f"/session/{sid}/train")
        assert trained.status_code == 200, trained.text
        assert trained.json()["status"] == "ok"
        assert trained.json()["n_samples"] == 4

        with client.websocket_connect(f"/session/{sid}/stream") as ws:
            ws.send_bytes(frame({"v": 2, "frameId": "smoke"}, payload))
            result = ws.receive_json()

        assert result["ok"] is True, result
        assert result["status"] == "ok"
        assert math.isfinite(result["x"])
        assert math.isfinite(result["y"])
        assert 0.0 <= result["x"] <= 1.0
        assert 0.0 <= result["y"] <= 1.0
