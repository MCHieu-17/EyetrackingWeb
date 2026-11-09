"""Worker chuyển đổi slide upload (PDF/PPTX/PPT/ODP) thành PDF + slide rows.

Chạy tách khỏi API để LibreOffice không chặn request và có thể giới hạn
concurrency. Job nằm trong PostgreSQL nên restart không mất việc.
"""

import asyncio
import logging

from app.core.config import settings
from app.services.content import process_pending_slide_imports
from app.worker_loop import run_worker_loop


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    await run_worker_loop(
        "content",
        settings.content_worker_poll_seconds,
        process_pending_slide_imports,
        limit=1,
        unit="slide import job(s)",
    )


if __name__ == "__main__":
    asyncio.run(main())
