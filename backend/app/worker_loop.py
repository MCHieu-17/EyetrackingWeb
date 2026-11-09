"""Vòng lặp worker dùng chung cho các background worker.

Mỗi worker chỉ cần cung cấp hàm `step` (một lượt xử lý) và khoảng poll;
phần log/catch exception/sleep được xử lý ở đây.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger("app.worker_loop")

Step = Callable[..., Awaitable[int | None]]


async def run_worker_loop(
    name: str,
    poll_seconds: float,
    step: Step,
    *,
    limit: int | None = None,
    max_iterations: int | None = None,
    unit: str = "item(s)",
) -> None:
    """Chạy `step` lặp lại, cách nhau `poll_seconds`.

    `limit` được truyền vào `step(limit=...)` khi khác None. `max_iterations`
    chỉ dùng cho test; None nghĩa là chạy vô hạn.
    """
    logger.info("%s worker started", name)
    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        iterations += 1
        try:
            processed = await step(limit=limit) if limit is not None else await step()
            if processed:
                logger.info("processed %s %s", processed, unit)
        except Exception:  # noqa: BLE001
            logger.exception("%s worker iteration failed", name)
        if max_iterations is not None and iterations >= max_iterations:
            break
        await asyncio.sleep(poll_seconds)
