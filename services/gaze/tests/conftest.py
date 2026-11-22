"""Fixture gaze: runtime thật + CPU/GPU stage giả, không cần model/GPU."""

from __future__ import annotations

import json
import struct
import time
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.api import session as session_api
from app.main import app
from app.services.errors import InvalidImage
from app.services.runtime import InferenceRuntime
from app.services.sessions import SessionManager
from app.settings import Settings


@dataclass
class FakePrepared:
    payload: bytes


class FakeCpu:
    def prepare(self, data: bytes | memoryview):
        payload = bytes(data)
        if payload == b"bad":
            raise InvalidImage("bad image")
        if payload == b"noface":
            return None
        return FakePrepared(payload)

    def warmup(self):
        return None


class FakeGpu:
    device = "cpu"
    model_name = "fake-unigaze"
    precision = "fp32"
    gpu_name = None
    is_cuda = False

    def __init__(self, mapping: dict[bytes, tuple[float, float]] | None = None):
        self.mapping = mapping or {}

    def predict(self, prepared: FakePrepared) -> tuple[float, float]:
        return self.mapping.get(prepared.payload, (0.1, 0.2))

    def warmup(self):
        return None


def runtime_settings(**overrides) -> Settings:
    values = {
        "device": "cpu",
        "unigaze_model": "unigaze_b16_joint",
        "max_queue": 8,
        "frame_max_age_ms": 10_000,
        "inference_timeout_s": 5.0,
        "gaze_fps": 15,
        "min_samples": 1,
        "max_samples_per_point": 50,
    }
    values.update(overrides)
    return Settings(**values)


MAPPING = {
    b"p00": (0.0, 0.0),
    b"p10": (1.0, 0.0),
    b"p01": (0.0, 1.0),
    b"p11": (1.0, 1.0),
    b"mid": (0.5, 0.5),
}


@pytest.fixture
def gaze_runtime(monkeypatch) -> Iterator[InferenceRuntime]:
    runtime = InferenceRuntime(
        runtime_settings(),
        cpu_stage_factory=FakeCpu,
        gpu_stage_factory=lambda: FakeGpu(MAPPING),
    )
    runtime.start()
    monkeypatch.setattr(session_api, "runtime", runtime)
    monkeypatch.setattr(
        session_api, "sessions", SessionManager(session_api.settings)
    )
    try:
        yield runtime
    finally:
        runtime.close()


@pytest.fixture
def client(gaze_runtime) -> TestClient:
    # Không dùng context manager để tránh lifespan load model thật.
    return TestClient(app)


def frame(header: dict | None, jpeg: bytes = b"mid") -> bytes:
    if header is None:
        return jpeg
    raw = json.dumps(header).encode()
    return struct.pack(">I", len(raw)) + raw + jpeg


def wait_throttle(client: TestClient, sid: str, seconds: float = 0.08) -> None:
    time.sleep(seconds)
