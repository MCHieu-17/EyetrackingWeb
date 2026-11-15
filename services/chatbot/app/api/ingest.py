"""API index slide vào pgvector."""

import asyncio
import logging
import threading

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
_job_lock = threading.Lock()


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


def _run(func, *args) -> tuple[int, int, list[str]]:
    with _job_lock:
        return func(*args)


async def _run_async(func, *args) -> tuple[int, int, list[str]]:
    return await asyncio.to_thread(_run, func, *args)


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
            get_ingestion().embed_slides,
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
        stats = await _run_async(get_ingestion().reindex_all)
    except VLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except DB_ERRORS as exc:
        raise _db_unavailable(exc) from exc
    except Exception as exc:  # noqa: BLE001
        raise _ingest_failed(exc) from exc
    return _result(stats)
