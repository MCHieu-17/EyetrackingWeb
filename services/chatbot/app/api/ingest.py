"""API nạp (ingest) slide vào pgvector.

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
    """Khởi tạo Ingestion một lần duy nhất (lazy)."""
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
    """Embedding (hoặc cập nhật) một slide đơn lẻ."""
    try:
        stats = await _run_async(get_ingestion().embed_slide, payload.lesson_content_id)
    except LookupError:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy slide: {payload.lesson_content_id}",
        )
    except VLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return _result(stats)


@router.post("/lesson", response_model=IngestResult)
async def embed_lesson(payload: IngestLessonRequest):
    """Embedding toàn bộ slide của một bài học."""
    try:
        stats = await _run_async(get_ingestion().embed_lesson, payload.lesson_id)
    except LookupError:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy bài học: {payload.lesson_id}",
        )
    except VLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return _result(stats)


@router.post("/course", response_model=IngestResult)
async def embed_course(payload: IngestCourseRequest):
    """Embedding toàn bộ slide của một khóa học."""
    try:
        stats = await _run_async(get_ingestion().embed_course, payload.course_id)
    except LookupError:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy khóa học: {payload.course_id}",
        )
    except VLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return _result(stats)


@router.post("/reindex-all", response_model=IngestResult)
async def reindex_all():
    """Backfill các slide chưa ready (dùng cho admin/CLI)."""
    try:
        stats = await _run_async(get_ingestion().reindex_all)
    except VLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return _result(stats)
