"""Batch GPU xuyên session, timeout cancel và queue đầy."""

from __future__ import annotations

import asyncio
import time

import pytest

from app.services.runtime import InferenceRuntime
from tests.conftest import FakeCpu, FakePrepared, runtime_settings

pytestmark = pytest.mark.fast


class BatchGpu:
    """Stage giả ghi lại kích thước batch và trả pitch theo payload."""

    device = "cpu"
    model_name = "fake-batch"
    precision = "fp32"
    gpu_name = None
    is_cuda = False

    def __init__(self, delay: float = 0.03):
        self.delay = delay
        self.batches: list[list[bytes]] = []

    def predict_batch(self, prepareds: list[FakePrepared]):
        self.batches.append([item.payload for item in prepareds])
        time.sleep(self.delay)
        return [
            (float(int.from_bytes(item.payload, "big")), 0.0)
            for item in prepareds
        ]

    def warmup(self) -> None:
        return None


def _runtime(gpu: BatchGpu, **overrides) -> InferenceRuntime:
    values = {
        "gpu_queue": 8,
        "gpu_batch": 8,
        "inference_timeout_s": 5.0,
    }
    values.update(overrides)
    settings = runtime_settings(**values)
    return InferenceRuntime(
        settings,
        cpu_stage_factory=FakeCpu,
        gpu_stage_factory=lambda: gpu,
    )


def test_gpu_batches_jobs_from_multiple_sessions():
    gpu = BatchGpu(delay=0.03)
    runtime = _runtime(gpu)
    runtime.start()
    try:

        async def run():
            jobs = [
                runtime.new_job(jpeg=bytes([index + 1]), session=None)
                for index in range(8)
            ]
            return await asyncio.gather(*(runtime.submit(job) for job in jobs))

        results = asyncio.run(run())
    finally:
        runtime.close()

    assert max(len(batch) for batch in gpu.batches) >= 2
    assert {int(result.pitch) for result in results} == set(range(1, 9))
    assert all(result.status == "ok" for result in results)


def test_timeout_cancels_queued_job():
    gpu = BatchGpu(delay=0.2)
    runtime = _runtime(
        gpu,
        gpu_batch=4,
        gpu_queue=4,
        inference_timeout_s=0.01,
    )
    runtime.start()
    try:

        async def run():
            return await runtime.submit(
                runtime.new_job(jpeg=b"\x01", session=None)
            )

        result = asyncio.run(run())
        snapshot = runtime.stats.snapshot()
    finally:
        runtime.close()

    assert result.status == "error"
    assert snapshot["dropped"].get("timeout") == 1


def test_full_gpu_queue_returns_overloaded():
    gpu = BatchGpu(delay=0.2)
    runtime = _runtime(gpu, gpu_batch=1, gpu_queue=1)
    runtime.start()
    try:

        async def run():
            jobs = [
                runtime.new_job(jpeg=bytes([index + 1]), session=None)
                for index in range(5)
            ]
            return await asyncio.gather(*(runtime.submit(job) for job in jobs))

        results = asyncio.run(run())
    finally:
        runtime.close()

    assert any(result.status == "overloaded" for result in results)
