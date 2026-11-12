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
from app.db import DatabaseUnavailableError, close_pool, get_pool  # noqa: E402
from app.settings import validate as validate_settings  # noqa: E402
from app.workflow.providers import get_embedding  # noqa: E402
from app.workflow.retrieval import close_retriever  # noqa: E402

logger = logging.getLogger("app.chat")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Khởi tạo pool + warm-up embedding một lần, giải phóng khi tắt service."""
    validate_settings()
    # Warm-up embedding (local: load weights) để /ready phản ánh đúng và
    # request đầu không phải chờ load model.
    embedding = await run_in_threadpool(get_embedding)
    await embedding.aembed_query("warm up")
    try:
        get_pool()
    except DatabaseUnavailableError:
        # Không chặn service khởi động: /ready sẽ trả 503 kèm lý do, còn ingest
        # trả 503 thay vì 500. Khi role/DB được sửa, pool tự kết nối lại.
        logger.exception("Không mở được DB pool lúc khởi động")

    try:
        yield
    finally:
        close_retriever()
        close_ingestion()
        close_pool()
        embedding.close()
        from app.workflow.llm import get_llm_client
        from app.workflow.lms import backend_client
        await get_llm_client().close()
        await backend_client().aclose()


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
    except Exception as exc:  # noqa: BLE001
        # Trả lý do thật (sai role/password, DB chưa lên...) để người vận hành
        # sửa ngay, không phải đoán từ log container.
        return JSONResponse(
            {"status": "degraded", "detail": str(exc)[:500]},
            status_code=503,
        )
    return {"status": "ok"}
