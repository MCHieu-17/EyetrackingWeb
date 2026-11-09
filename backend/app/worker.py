"""Metrics/analysis worker.

Chạy các `analysis_runs` pending trong PostgreSQL. Watermark và trạng thái nằm
trong DB nên restart không mất việc; Redis chỉ là cache/throttle.
"""

import asyncio
import logging

from app.core.config import settings
from app.services.analysis import execute_pending_runs

logger = logging.getLogger("app.worker")
POLL_SECONDS = settings.worker_poll_seconds


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info("analysis worker started")
    while True:
        try:
            processed = await execute_pending_runs(limit=10)
            if processed:
                logger.info("processed %s analysis runs", processed)
        except Exception:  # noqa: BLE001
            logger.exception("analysis worker iteration failed")
        await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
