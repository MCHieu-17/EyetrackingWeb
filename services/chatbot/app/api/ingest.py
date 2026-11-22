"""API index slide vào pgvector."""

import asyncio
import logging
import threading
from contextlib import contextmanager

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from psycopg_pool import PoolTimeout

from app.api.chat import require_internal_token
from app.db import DatabaseUnavailableError
from app.schemas import IngestResult, IngestSlidesRequest
from app.services.ingest import Ingestion, VLMUnavailableError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ingest",
    tags=["ingest"],
    dependencies=[Depends(require_internal_token)],
)

_ingestion: Ingestion | None = None
_init_lock = threading.Lock()
# Single-flight theo lesson + trần số job ingest chạy song song. Hai lesson
# khác nhau vẫn ingest đồng thời; request trùng lesson xếp hàng rồi thấy slide
# đã ready và bỏ qua.
_job_locks: dict[tuple[str, ...], threading.Lock] = {}
_job_locks_guard = threading.Lock()
_job_capacity = threading.BoundedSemaphore(2)


def get_ingestion() -> Ingestion:
    global _ingestion
    if _ingestion is None:
        with _init_lock:
            if _ingestion is None:
                _ingestion = Ingestion()
    return _ingestion


def close_ingestion() -> None:
    global _ingestion
    if _ingestion is not None:
        _ingestion.close()
        _ingestion = None


@contextmanager
def _job_slot(keys: tuple[str, ...]):
    with _job_locks_guard:
        lock = _job_locks.setdefault(keys, threading.Lock())
    lock.acquire()
    _job_capacity.acquire()
    try:
        yield
    finally:
        _job_capacity.release()
        lock.release()


def _run_ingest(ingestion: Ingestion, slide_ids: list[str]):
    with _job_slot(ingestion.job_keys(slide_ids)):
        return ingestion.embed_slides(slide_ids)


def _run_reindex_all(ingestion: Ingestion):
    with _job_slot(("reindex-all",)):
        return ingestion.reindex_all()


async def _run_async(func, *args) -> tuple[int, int, list[str]]:
    return await asyncio.to_thread(func, *args)


def _result(stats: tuple[int, int, list[str]]) -> IngestResult:
    processed, failed, errors = stats
    return IngestResult(processed=processed, failed=failed, errors=errors)


DB_ERRORS = (DatabaseUnavailableError, PoolTimeout, psycopg.Error)


def _db_unavailable(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail=f"Không truy cập được PostgreSQL cho chatbot: {exc}",
    )


def _ingest_failed(exc: Exception) -> HTTPException:
    logger.exception("Ingest thất bại")
    return HTTPException(status_code=503, detail=f"Ingest thất bại: {exc}")


@router.post("/slides", response_model=IngestResult)
async def embed_slides(payload: IngestSlidesRequest):
    try:
        stats = await _run_async(
            _run_ingest,
            get_ingestion(),
            payload.slide_ids,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Không tìm thấy slide")
    except VLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except DB_ERRORS as exc:
        raise _db_unavailable(exc) from exc
    except Exception as exc:  # noqa: BLE001
        raise _ingest_failed(exc) from exc
    return _result(stats)


@router.post("/reindex-all", response_model=IngestResult)
async def reindex_all():
    try:
        stats = await _run_async(_run_reindex_all, get_ingestion())
    except VLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except DB_ERRORS as exc:
        raise _db_unavailable(exc) from exc
    except Exception as exc:  # noqa: BLE001
        raise _ingest_failed(exc) from exc
    return _result(stats)
