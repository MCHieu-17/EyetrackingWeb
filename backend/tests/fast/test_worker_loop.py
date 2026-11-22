"""Worker loop: sleep ngắn khi vừa có việc, poll dài khi idle."""

from __future__ import annotations

import pytest

from app import worker_loop

pytestmark = pytest.mark.fast


async def test_worker_loop_uses_short_sleep_when_busy(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    results = iter([1, 0, 0])

    async def step(**_kwargs):
        return next(results)

    monkeypatch.setattr(worker_loop.asyncio, "sleep", fake_sleep)
    await worker_loop.run_worker_loop(
        "test", 5.0, step, max_iterations=3
    )
    assert sleeps == [0.2, 5.0]
