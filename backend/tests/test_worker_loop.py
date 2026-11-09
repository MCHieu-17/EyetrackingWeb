import asyncio
import logging

import pytest

from app.worker_loop import run_worker_loop


@pytest.mark.asyncio
async def test_run_worker_loop_calls_step_with_limit(caplog):
    caplog.set_level(logging.INFO)
    calls: list[int | None] = []

    async def step(*, limit: int | None = None) -> int:
        calls.append(limit)
        return 2

    await run_worker_loop("test", 0, step, limit=5, max_iterations=1)

    assert calls == [5]
    assert "test worker started" in caplog.text
    assert "processed 2 item(s)" in caplog.text


@pytest.mark.asyncio
async def test_run_worker_loop_calls_step_without_limit():
    calls = 0

    async def step() -> None:
        nonlocal calls
        calls += 1

    await run_worker_loop("test", 0, step, max_iterations=1)

    assert calls == 1


@pytest.mark.asyncio
async def test_run_worker_loop_continues_after_exception(caplog):
    caplog.set_level(logging.ERROR)
    calls = 0

    async def step() -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("boom")
        return 1

    await run_worker_loop("test", 0, step, max_iterations=2)

    assert calls == 2
    assert "test worker iteration failed" in caplog.text


@pytest.mark.asyncio
async def test_run_worker_loop_is_cancellable():
    started = asyncio.Event()

    async def step() -> None:
        started.set()
        await asyncio.Event().wait()

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(run_worker_loop("test", 0, step), timeout=0.05)

    assert started.is_set()
