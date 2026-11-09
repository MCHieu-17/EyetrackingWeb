"""Metrics/analysis worker.

Chạy các `analysis_runs` pending trong PostgreSQL. Watermark và trạng thái nằm
trong DB nên restart không mất việc; Redis chỉ là cache/throttle.
"""

import asyncio
import logging

from app.core.config import settings
from app.services.analysis import execute_pending_runs
from app.worker_loop import run_worker_loop

POLL_SECONDS = settings.worker_poll_seconds


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    await run_worker_loop(
        "analysis",
        POLL_SECONDS,
        execute_pending_runs,
        limit=10,
        unit="analysis runs",
    )


if __name__ == "__main__":
    asyncio.run(main())
