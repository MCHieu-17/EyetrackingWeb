"""Worker chuyển đổi slide upload (PDF/PPTX/PPT/ODP) thành PDF + slide rows.

Chạy tách khỏi API để LibreOffice không chặn request và có thể giới hạn
concurrency. Job nằm trong PostgreSQL nên restart không mất việc.
"""

import asyncio
import logging
import os

from app.services.content import process_pending_slide_imports

logger = logging.getLogger("app.content_worker")
POLL_SECONDS = float(os.getenv("CONTENT_WORKER_POLL_SECONDS", "3"))


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info("content worker started")
    while True:
        try:
            processed = await process_pending_slide_imports(limit=1)
            if processed:
                logger.info("processed %s slide import job(s)", processed)
        except Exception:  # noqa: BLE001
            logger.exception("content worker iteration failed")
        await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
