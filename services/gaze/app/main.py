"""Gaze API — FastAPI app cho ước lượng hướng nhìn + calibration.

Chạy:
    uvicorn app.main:app --host 0.0.0.0 --port 8000

Tài liệu đầy đủ các endpoint: README.md cùng thư mục.

Endpoint vận hành:
    GET /health  -> liveness + thống kê runtime, luôn 200 khi tiến trình sống
    GET /ready   -> readiness, 503 khi pipeline (landmarker + unigaze) chưa load
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api import session as session_api

logger = logging.getLogger("app.gaze")


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_api.settings.validate()
    session_api.runtime.start()  # load landmarker + unigaze + warmup
    task = asyncio.create_task(cleanup_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        session_api.runtime.close()


app = FastAPI(title="Gaze API", lifespan=lifespan)
app.include_router(session_api.router)


async def cleanup_loop():
    """Xoá session hết TTL mỗi phút (giới hạn MAX_SESSIONS)."""
    while True:
        await asyncio.sleep(60)
        session_api.sessions.cleanup_expired()


def _status() -> dict:
    status = session_api.runtime.snapshot()
    status["sessions"] = session_api.sessions.stats()
    return status


@app.get("/health")
def health():
    """Liveness: tiến trình HTTP còn phản hồi + thống kê pipeline."""
    return _status()


@app.get("/ready")
def ready():
    """Readiness: chỉ 200 khi pipeline đã load xong, ngược lại 503."""
    status = _status()
    if not status["pipeline_ready"]:
        return JSONResponse(status, status_code=503)
    return status


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
