"""FastAPI service bọc pipeline RAG.

Chạy:
    uvicorn app.main:app --reload

Endpoint vận hành:
    GET /health -> liveness, luôn 200
    GET /ready  -> readiness, 503 khi DB không truy cập được
"""

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from fastapi import FastAPI  # noqa: E402
from fastapi.concurrency import run_in_threadpool  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from app.api.chat import router as chat_router  # noqa: E402
from app.api.ingest import close_ingestion  # noqa: E402
from app.api.ingest import router as ingest_router  # noqa: E402
from app.db import close_pool, get_pool  # noqa: E402
from app.settings import validate as validate_settings  # noqa: E402
from app.workflow.providers import get_embedding  # noqa: E402
from app.workflow.retrieval import close_retriever  # noqa: E402

logger = logging.getLogger("app.chat")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Khởi tạo pool + warm-up embedding một lần, giải phóng khi tắt service."""
    validate_settings()
    # Warm-up embedding (local: load weights lên GPU) để /ready phản ánh đúng và
    # request đầu không phải chờ load model.
    await run_in_threadpool(get_embedding)
    get_pool()

    try:
        yield
    finally:
        close_retriever()
        close_ingestion()
        close_pool()


app = FastAPI(title="LMS Study Chatbot", lifespan=lifespan)
app.include_router(chat_router)
app.include_router(ingest_router)


def _db_reachable() -> None:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    try:
        await run_in_threadpool(_db_reachable)
    except Exception:
        return JSONResponse({"status": "degraded"}, status_code=503)
    return {"status": "ok"}
