"""Test HTTP + WebSocket với runtime giả (không cần GPU/model)."""

import asyncio
import json
import struct
import time
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api import session as session_api
from app.main import app
from app.services.errors import InferenceOverloaded
from app.services.runtime import FrameJob, GazeFrame, RuntimeStats


class FakeRuntime:
    def __init__(self):
        self.stats = RuntimeStats()
        self.ready = True
        self.mode = "ok"

    def pipeline_ready(self):
        return self.ready

    def suggested_fps(self):
        return 7

    def snapshot(self):
        return {
            "status": "ok" if self.ready else "degraded",
            "pipeline_ready": self.ready,
            "device": "cpu",
            "model": "fake",
            "precision": "fp32",
            "gpu_available": False,
            "gpu_name": None,
            "queue": {"cpu": 0, "gpu": 0},
            "stats": self.stats.snapshot(),
        }

    def new_job(self, *, jpeg, session=None, header=None):
        loop = asyncio.get_running_loop()
        return FrameJob(
            jpeg=jpeg,
            received_at=time.monotonic(),
            loop=loop,
            future=loop.create_future(),
            session=session,
            header=header,
        )

    async def submit(self, job):
        if self.mode == "overload":
            raise InferenceOverloaded("full")
        return GazeFrame("ok", x=0.25, y=0.5)


def frame(header: dict, jpeg: bytes = b"\xff\xd8jpeg") -> bytes:
    raw = json.dumps(header).encode()
    return struct.pack(">I", len(raw)) + raw + jpeg


@pytest.fixture
def fake_runtime(monkeypatch):
    fake = FakeRuntime()
    monkeypatch.setattr(session_api, "runtime", fake)
    return fake


def ready_session() -> str:
    sid = session_api.sessions.create({"c": (0.5, 0.5)})
    session_api.sessions.get(sid).mark_ready()
    return sid


def test_health_reports_runtime_and_sessions(fake_runtime):
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["pipeline_ready"] is True
    assert body["stats"]["frames_in"] == 0
    assert "total" in body["sessions"]


def test_ready_returns_503_when_pipeline_not_ready(fake_runtime):
    fake_runtime.ready = False
    client = TestClient(app)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["pipeline_ready"] is False


def test_ws_echoes_header_and_returns_point(fake_runtime):
    sid = ready_session()
    client = TestClient(app)
    header = {
        "v": 2,
        "frameId": "f-1",
        "sequence": 3,
        "captureMonotonicNs": 42,
        "eventTime": "2026-11-18T00:00:00Z",
        "presentationId": "p-1",
        "layoutGeneration": 2,
    }
    with client.websocket_connect(f"/session/{sid}/stream") as ws:
        ws.send_bytes(frame(header))
        data = ws.receive_json()

    assert data["ok"] is True
    assert data["status"] == "ok"
    assert data["x"] == pytest.approx(0.25)
    assert data["y"] == pytest.approx(0.5)
    assert data["frameId"] == "f-1"
    assert data["sequence"] == 3
    assert data["presentationId"] == "p-1"
    assert "suggestedFps" not in data


def test_ws_returns_overloaded_with_suggested_fps(fake_runtime):
    fake_runtime.mode = "overload"
    sid = ready_session()
    client = TestClient(app)
    header = {"v": 2, "frameId": "f-2", "sequence": 1}
    with client.websocket_connect(f"/session/{sid}/stream") as ws:
        ws.send_bytes(frame(header))
        data = ws.receive_json()
    assert data["status"] == "overloaded"
    assert data["suggestedFps"] == 7


def test_ws_rejects_oversized_frame(fake_runtime, monkeypatch):
    sid = ready_session()
    monkeypatch.setattr(
        session_api,
        "settings",
        replace(session_api.settings, max_frame_bytes=4),
    )
    client = TestClient(app)
    with client.websocket_connect(f"/session/{sid}/stream") as ws:
        ws.send_bytes(frame({"v": 2, "frameId": "f-3"}, jpeg=b"12345"))
        # Frame bị bỏ; chờ qua cửa sổ throttle rồi gửi frame hợp lệ.
        time.sleep(0.08)
        ws.send_bytes(frame({"v": 2, "frameId": "f-4"}, jpeg=b"123"))
        data = ws.receive_json()
    assert data["frameId"] == "f-4"


def test_ws_closes_uncalibrated_session(fake_runtime):
    sid = session_api.sessions.create({"c": (0.5, 0.5)})
    client = TestClient(app)
    with client.websocket_connect(f"/session/{sid}/stream") as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
    assert exc.value.code == 1008


def test_ws_closes_when_pipeline_not_ready(fake_runtime):
    fake_runtime.ready = False
    sid = ready_session()
    client = TestClient(app)
    with client.websocket_connect(f"/session/{sid}/stream") as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
    assert exc.value.code == 1013
