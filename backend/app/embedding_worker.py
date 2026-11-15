"""Worker đồng bộ index RAG từ `background_jobs(kind=index_slides)`.

Job nằm trong PostgreSQL nên restart không mất việc; nhiều replica backend
dùng chung hàng đợi và worker claim bằng `FOR UPDATE SKIP LOCKED`.
"""

import asyncio
import logging

from app.core.config import settings
from app.services.embedding_jobs import process_pending_jobs
from app.worker_loop import run_worker_loop


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    await run_worker_loop(
        "embedding",
        settings.embedding_worker_poll_seconds,
        process_pending_jobs,
        limit=1,
        unit="embedding job(s)",
    )


if __name__ == "__main__":
    asyncio.run(main())
