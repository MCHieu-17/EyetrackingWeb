"""Test hồi quy tuyến tính thật qua HTTP/WS (không mock Calibration)."""

from __future__ import annotations

import time

import pytest
import ubjson

from tests.conftest import frame

pytestmark = pytest.mark.fast

POINTS = [
    {"id": "p00", "x": 0.1, "y": 0.2},
    {"id": "p10", "x": 0.9, "y": 0.2},
    {"id": "p01", "x": 0.1, "y": 0.8},
    {"id": "p11", "x": 0.9, "y": 0.8},
]


def _train(client):
    sid = client.post("/session", json={"points": POINTS}).json()["session_id"]
    for point in POINTS:
        response = client.post(
            f"/session/{sid}/calibrate",
            files={
                "image": ("face.jpg", point["id"].encode(), "image/jpeg")
            },
            data={"point_id": point["id"]},
        )
        assert response.status_code == 200, response.text
    trained = client.post(f"/session/{sid}/train")
    assert trained.status_code == 200, trained.text
    assert trained.json() == {"status": "ok", "n_samples": 4}
    return sid


def _first_point(client, sid, payload: bytes) -> dict:
    time.sleep(0.08)
    with client.websocket_connect(f"/session/{sid}/stream") as ws:
        ws.send_bytes(frame({"v": 2, "frameId": "f-1"}, payload))
        return ws.receive_json()


def test_linear_regression_maps_pitch_yaw_to_viewport(client):
    sid = _train(client)
    model = client.get(f"/session/{sid}/model").content
    for point in POINTS:
        target = client.post(
            "/session", json={"points": [{"id": "only", "x": 0.5, "y": 0.5}]}
        ).json()["session_id"]
        imported = client.post(
            f"/session/{target}/import",
            files={"model": ("calibration.ubj", model, "application/octet-stream")},
        )
        assert imported.status_code == 200
        data = _first_point(client, target, point["id"].encode())
        assert data["ok"] is True
        assert data["status"] == "ok"
        assert data["x"] == pytest.approx(point["x"], abs=1e-6)
        assert data["y"] == pytest.approx(point["y"], abs=1e-6)


def test_exported_model_reproduces_mapping_in_new_session(client):
    sid = _train(client)
    model = client.get(f"/session/{sid}/model")
    assert model.status_code == 200

    target = client.post(
        "/session", json={"points": [{"id": "only", "x": 0.5, "y": 0.5}]}
    ).json()["session_id"]
    imported = client.post(
        f"/session/{target}/import",
        files={"model": ("calibration.ubj", model.content, "application/octet-stream")},
    )
    assert imported.status_code == 200
    assert imported.json()["status"] == "ready"

    data = _first_point(client, target, b"mid")
    assert data["x"] == pytest.approx(0.5)
    assert data["y"] == pytest.approx(0.5)


def test_import_rejects_wrong_ubj_format(client):
    sid = client.post(
        "/session", json={"points": [{"id": "only", "x": 0.5, "y": 0.5}]}
    ).json()["session_id"]
    payload = ubjson.dumpb(
        {"format": "gaze-lr-v1", "coef": [[1, 0], [0, 1]], "intercept": [0, 0]}
    )
    response = client.post(
        f"/session/{sid}/import",
        files={"model": ("old.ubj", payload, "application/octet-stream")},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "invalid_model"}
