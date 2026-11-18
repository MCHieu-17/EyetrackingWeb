"""Tests cho runtime 2 tầng: deadline, overload, stats (không cần GPU)."""

import asyncio
import time

import pytest

from app.services.errors import InferenceOverloaded, InvalidImage
from app.services.runtime import InferenceRuntime
from app.services.sessions import Session
from app.settings import Settings


class FakeCpu:
    def __init__(self, delay: float = 0.0):
        self.delay = delay

    def prepare(self, data):
        if self.delay:
            time.sleep(self.delay)
        if data == b"bad":
            raise InvalidImage("hỏng")
        if data == b"noface":
            return None
        return object()

    def warmup(self):
        pass


class FakeGpu:
    device = "cpu"
    model_name = "fake-unigaze"
    precision = "fp32"
    gpu_name = None
    is_cuda = False

    def predict(self, prepared):
        return 0.1, 0.2

    def warmup(self):
        pass


def make_settings(**overrides) -> Settings:
    values = {
        "device": "cpu",
        "unigaze_model": "unigaze_b16_joint",
        "max_queue": 2,
        "frame_max_age_ms": 100,
        "inference_timeout_s": 2.0,
    }
    values.update(overrides)
    return Settings(**values)


def make_runtime(cpu_delay: float = 0.0, **overrides) -> InferenceRuntime:
    settings = make_settings(**overrides)
    return InferenceRuntime(
        settings,
        cpu_stage_factory=lambda: FakeCpu(cpu_delay),
        gpu_stage_factory=FakeGpu,
    )


def run_with(runtime: InferenceRuntime, coro_factory):
    runtime.start()
    try:
        return asyncio.run(coro_factory())
    finally:
        runtime.close()


def test_calibration_job_returns_pitch_and_yaw():
    runtime = make_runtime()

    async def scenario():
        job = runtime.new_job(jpeg=b"ok")
        runtime.stats.count_in()
        return await runtime.submit(job)

    result = run_with(runtime, scenario)
    assert result.status == "ok"
    assert result.pitch == pytest.approx(0.1)
    assert result.yaw == pytest.approx(0.2)
    assert runtime.snapshot()["stats"]["frames_inferred"] == 1


def test_stream_job_applies_calibration_and_smoothing():
    runtime = make_runtime()
    settings = make_settings()
    session = Session({"c": (0.5, 0.5)}, settings)
    session.calib.fit(
        [(0, 0), (1, 0), (0, 1), (1, 1)],
        [(0.2, 0.3), (0.8, 0.3), (0.2, 0.7), (0.8, 0.7)],
    )
    session.mark_ready()

    async def scenario():
        job = runtime.new_job(jpeg=b"ok", session=session)
        runtime.stats.count_in()
        return await runtime.submit(job)

    result = run_with(runtime, scenario)
    assert result.status == "ok"
    assert result.x == pytest.approx(0.26)
    assert result.y == pytest.approx(0.38)


def test_no_face_is_not_counted_as_overload_drop():
    runtime = make_runtime()

    async def scenario():
        job = runtime.new_job(jpeg=b"noface")
        runtime.stats.count_in()
        return await runtime.submit(job)

    result = run_with(runtime, scenario)
    snapshot = runtime.snapshot()["stats"]
    assert result.status == "no_face"
    assert snapshot["no_face"] == 1
    assert snapshot["dropped"] == {}
    assert snapshot["frames_inferred"] == 0


def test_invalid_image_status_and_drop_counter():
    runtime = make_runtime()

    async def scenario():
        job = runtime.new_job(jpeg=b"bad")
        runtime.stats.count_in()
        return await runtime.submit(job)

    result = run_with(runtime, scenario)
    snapshot = runtime.snapshot()["stats"]
    assert result.status == "invalid_image"
    assert snapshot["dropped"] == {"invalid_image": 1}


def test_stale_frame_is_dropped_before_inference():
    runtime = make_runtime()

    async def scenario():
        job = runtime.new_job(jpeg=b"ok")
        job.received_at -= 1.0
        runtime.stats.count_in()
        return await runtime.submit(job)

    result = run_with(runtime, scenario)
    snapshot = runtime.snapshot()["stats"]
    assert result.status == "stale"
    assert snapshot["dropped"] == {"stale": 1}
    assert snapshot["overload_rate"] == pytest.approx(1.0)


def test_full_queue_raises_overloaded_immediately():
    runtime = make_runtime(cpu_delay=0.2, max_queue=1)

    async def scenario():
        first = asyncio.create_task(
            runtime.submit(runtime.new_job(jpeg=b"ok"))
        )
        await asyncio.sleep(0.05)  # CPU thread đã nhận job đầu
        second = asyncio.create_task(
            runtime.submit(runtime.new_job(jpeg=b"ok"))
        )
        await asyncio.sleep(0.01)  # job thứ hai lấp đầy queue
        with pytest.raises(InferenceOverloaded):
            await runtime.submit(runtime.new_job(jpeg=b"ok"))
        await asyncio.gather(first, second)

    run_with(runtime, scenario)
    assert runtime.snapshot()["stats"]["dropped"]["overload"] == 1


def test_snapshot_reports_runtime_config():
    runtime = make_runtime()
    runtime.start()
    try:
        snapshot = runtime.snapshot()
    finally:
        runtime.close()
    assert snapshot["pipeline_ready"] is True
    assert snapshot["model"] == "fake-unigaze"
    assert snapshot["device"] == "cpu"
    assert snapshot["queue"] == {"cpu": 0, "gpu": 0}
