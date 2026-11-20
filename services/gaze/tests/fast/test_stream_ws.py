"""WS protocol v2: echo, close code, throttle, no_face/invalid."""

from __future__ import annotations

import time
from dataclasses import replace

import pytest
from starlette.websockets import WebSocketDisconnect

from app.api import session as session_api
from tests.conftest import frame

pytestmark = pytest.mark.fast


def _ready_session(client):
    sid = client.post(
        "/session", json={"points": [{"id": "p00", "x": 0.1, "y": 0.2}]}
    ).json()["session_id"]
    response = client.post(
        f"/session/{sid}/calibrate",
        files={"image": ("face.jpg", b"p00", "image/jpeg")},
        data={"point_id": "p00"},
    )
    assert response.status_code == 200
    assert client.post(f"/session/{sid}/train").status_code == 200
    return sid


def test_uncalibrated_session_closes_1008(client):
    sid = client.post(
        "/session", json={"points": [{"id": "p00", "x": 0.1, "y": 0.2}]}
    ).json()["session_id"]
    with client.websocket_connect(f"/session/{sid}/stream") as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
    assert exc.value.code == 1008


def test_pipeline_not_ready_closes_1013(client, gaze_runtime):
    sid = _ready_session(client)
    gaze_runtime.close()
    with client.websocket_connect(f"/session/{sid}/stream") as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
    assert exc.value.code == 1013


def test_v2_header_echo(client):
    sid = _ready_session(client)
    header = {
        "v": 2,
        "frameId": "f-1",
        "sequence": 3,
        "captureMonotonicNs": 42,
        "eventTime": "2026-11-18T00:00:00Z",
        "presentationId": "p-1",
        "layoutGeneration": 2,
        "ignored": "x",
    }
    with client.websocket_connect(f"/session/{sid}/stream") as ws:
        ws.send_bytes(frame(header, b"p00"))
        data = ws.receive_json()
    assert data["ok"] is True
    assert data["status"] == "ok"
    assert data["x"] == pytest.approx(0.1)
    assert data["y"] == pytest.approx(0.2)
    for key in ("frameId", "sequence", "captureMonotonicNs", "eventTime", "presentationId", "layoutGeneration"):
        assert data[key] == header[key]
    assert "ignored" not in data


def test_legacy_jpeg_has_no_echo(client):
    sid = _ready_session(client)
    with client.websocket_connect(f"/session/{sid}/stream") as ws:
        ws.send_bytes(b"p00")
        data = ws.receive_json()
    assert data["status"] == "ok"
    assert "frameId" not in data


def test_no_face_and_invalid_image(client):
    sid = _ready_session(client)
    with client.websocket_connect(f"/session/{sid}/stream") as ws:
        ws.send_bytes(frame({"v": 2, "frameId": "noface"}, b"noface"))
        data = ws.receive_json()
        assert data["ok"] is False
        assert data["status"] == "no_face"

        time.sleep(0.08)
        ws.send_bytes(frame({"v": 2, "frameId": "bad"}, b"bad"))
        data = ws.receive_json()
        assert data["ok"] is False
        assert data["status"] == "invalid_image"


def test_oversized_frame_is_dropped(client, monkeypatch):
    sid = _ready_session(client)
    monkeypatch.setattr(
        session_api,
        "settings",
        replace(session_api.settings, max_frame_bytes=4),
    )
    with client.websocket_connect(f"/session/{sid}/stream") as ws:
        ws.send_bytes(frame({"v": 2, "frameId": "big"}, b"12345"))
        time.sleep(0.08)
        ws.send_bytes(frame({"v": 2, "frameId": "ok"}, b"p00"))
        data = ws.receive_json()
    assert data["frameId"] == "ok"


def test_throttle_drops_second_frame_in_window(client):
    sid = _ready_session(client)
    with client.websocket_connect(f"/session/{sid}/stream") as ws:
        ws.send_bytes(frame({"v": 2, "frameId": "first"}, b"p00"))
        first = ws.receive_json()
        assert first["frameId"] == "first"

        # Frame ngay sau bị throttle; frame sau cửa sổ được xử lý.
        ws.send_bytes(frame({"v": 2, "frameId": "dropped"}, b"p00"))
        time.sleep(0.08)
        ws.send_bytes(frame({"v": 2, "frameId": "third"}, b"p00"))
        third = ws.receive_json()
    assert third["frameId"] == "third"
