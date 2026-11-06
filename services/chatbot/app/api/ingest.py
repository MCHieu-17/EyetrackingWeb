"""API nạp (ingest) slide version vào pgvector.

`Ingestion` là tiến trình nặng: gọi VLM mô tả ảnh rồi embedding. Vì vậy ở đây
dùng lazy singleton (chỉ khởi tạo khi có request đầu tiên) và một khóa để các
job ingest không chạy chồng nhau, tránh quá tải VLM/DB.
"""

import asyncio
import logging
import threading

from fastapi import APIRouter, Depends, HTTPException

from app.api.chat import require_internal_token
from app.schemas import (
    IngestCourseRequest,
    IngestLessonRequest,
    IngestResult,
    IngestSlideRequest,
)
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


@router.post("/slide", response_model=IngestResult)
async def embed_slide(payload: IngestSlideRequest):
    try:
        stats = await _run_async(
            get_ingestion().embed_slide, payload.slide_version_id
        )
    except LookupError:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy slide version: {payload.slide_version_id}",
        )
    except VLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return _result(stats)


@router.post("/lesson-version", response_model=IngestResult)
async def embed_lesson_version(payload: IngestLessonRequest):
    try:
        stats = await _run_async(
            get_ingestion().embed_lesson_version, payload.lesson_version_id
        )
    except LookupError:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy lesson version: {payload.lesson_version_id}",
        )
    except VLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return _result(stats)


@router.post("/course-version", response_model=IngestResult)
async def embed_course_version(payload: IngestCourseRequest):
    try:
        stats = await _run_async(
            get_ingestion().embed_course_version, payload.course_version_id
        )
    except LookupError:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy course version: {payload.course_version_id}",
        )
    except VLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return _result(stats)


@router.post("/reindex-all", response_model=IngestResult)
async def reindex_all():
    try:
        stats = await _run_async(get_ingestion().reindex_all)
    except VLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return _result(stats)
