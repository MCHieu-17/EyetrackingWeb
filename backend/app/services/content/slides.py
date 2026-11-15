"""Slide import jobs, rendering and lesson contents."""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.auth import User
from app.models.background_job import BackgroundJob
from app.models.course import Course, CourseModule, Lesson, Slide
from app.models.media import MediaAsset
from app.services import media_storage, slide_aoi, slide_import
from app.services.content.common import (
    _not_found,
    _now,
    course_of_lesson,
    touch_course,
    touch_lesson,
)
from app.services.embedding_jobs import enqueue_index_lesson
from app.services.job_queue import claim_next_jobs, recover_stale_jobs

IMPORT_KIND = "import_slides"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def _asset_for_bytes(
    db: AsyncSession,
    *,
    course: Course,
    data: bytes,
    mime_type: str,
    object_key: str,
    page_count: int | None = None,
    source_format: str | None = None,
) -> MediaAsset:
    digest = _sha256(data)
    existing = (
        await db.execute(
            select(MediaAsset).where(
                MediaAsset.course_id == course.id,
                MediaAsset.sha256 == digest,
                MediaAsset.state == "ready",
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    await asyncio.to_thread(media_storage.put_bytes, object_key, data, mime_type)
    asset = MediaAsset(
        course_id=course.id,
        storage_backend="r2" if settings.r2_enabled else "local",
        object_key=object_key,
        sha256=digest,
        mime_type=mime_type,
        byte_size=len(data),
        state="ready",
        page_count=page_count,
        source_format=source_format,
    )
    db.add(asset)
    await db.flush()
    return asset


async def create_slide_import(
    db: AsyncSession,
    course: Course,
    user: User,
    lesson_id: str,
    data: bytes,
    filename: str,
    mime: str | None,
) -> BackgroundJob:
    """Nhận file upload, lưu tạm và tạo job chuyển đổi bất đồng bộ."""
    if len(data) > settings.max_upload_bytes:
        limit = settings.max_upload_bytes // (1024 * 1024)
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"File vượt quá {limit}MB cho phép.",
        )

    try:
        fmt = slide_import.detect_format(filename, mime, data)
        if fmt == "pdf":
            slide_import.validate_pdf(data)
    except slide_import.SlideImportError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    course_from_lesson, lesson = await course_of_lesson(db, lesson_id)
    if course_from_lesson.id != course.id:
        raise _not_found("Không tìm thấy bài học trong khóa")
    if lesson.kind != "lesson":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Chỉ bài giảng mới nhận tài liệu slide"
        )

    old_jobs = (
        await db.execute(
            select(BackgroundJob).where(
                BackgroundJob.lesson_id == lesson.id,
                BackgroundJob.kind == IMPORT_KIND,
                BackgroundJob.status.in_(("queued", "processing")),
            )
        )
    ).scalars().all()
    queued_staging_keys = [
        str((old.payload or {}).get("source_object_key"))
        for old in old_jobs
        if old.status == "queued" and (old.payload or {}).get("source_object_key")
    ]
    for old in old_jobs:
        old.status = "cancelled"
        old.finished_at = _now()
        old.updated_at = _now()

    job_id = str(uuid.uuid4())
    suffix = Path(filename or "").suffix.lower() or f".{fmt}"
    staging_key = (
        f"instances/{settings.app_instance_id}/courses/{course.id}/"
        f"lessons/{lesson_id}/imports/{job_id}/upload{suffix}"
    )
    job = BackgroundJob(
        id=job_id,
        lesson_id=lesson.id,
        kind=IMPORT_KIND,
        status="queued",
        payload={
            "created_by": user.id,
            "source_filename": filename or f"slides{suffix}",
            "source_mime": slide_import.mime_for_format(fmt),
            "source_size": len(data),
            "source_sha256": _sha256(data),
            "source_object_key": staging_key,
        },
    )
    db.add(job)
    touch_lesson(lesson)
    touch_course(course)
    await db.flush()

    try:
        await asyncio.to_thread(
            media_storage.put_bytes, staging_key, data, job.payload["source_mime"]
        )
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không lưu được file tạm để xử lý.",
        ) from exc

    for key in queued_staging_keys:
        try:
            await asyncio.to_thread(media_storage.delete_key, key)
        except Exception:  # noqa: BLE001
            pass
    return job


async def get_slide_import_job(
    db: AsyncSession, course: Course, lesson_id: str, job_id: str
) -> BackgroundJob:
    job = await db.get(BackgroundJob, job_id)
    if (
        job is None
        or job.kind != IMPORT_KIND
        or job.lesson_id != lesson_id
    ):
        raise _not_found("Không tìm thấy job tải tài liệu")
    _, lesson = await course_of_lesson(db, lesson_id)
    if lesson.id != job.lesson_id:
        raise _not_found("Không tìm thấy job tải tài liệu")
    return job


async def _delete_unreferenced_asset(
    db: AsyncSession, asset_id: str | None
) -> tuple[str, str] | None:
    if not asset_id:
        return None
    used = (
        await db.execute(
            select(Lesson.id).where(Lesson.pdf_asset_id == asset_id).limit(1)
        )
    ).first()
    if used is not None:
        return None
    asset = await db.get(MediaAsset, asset_id)
    if asset is None:
        return None
    row = (asset.object_key, asset.storage_backend)
    await db.delete(asset)
    return row


async def process_slide_import(job_id: str) -> None:
    """Worker: convert staging file -> PDF and replace slides in place."""
    async with SessionLocal() as db:
        job = await db.get(BackgroundJob, job_id)
        if (
            job is None
            or job.kind != IMPORT_KIND
            or job.status != "processing"
        ):
            return
        payload = job.payload or {}
        source_key = str(payload.get("source_object_key") or "")
        source_filename = str(payload.get("source_filename") or "slides")
        removed_keys: list[tuple[str, str]] = []
        remove_staging = False

        try:
            data = await asyncio.to_thread(media_storage.get_bytes, source_key)
            fmt = slide_import.detect_format(
                source_filename, str(payload.get("source_mime") or ""), data
            )
            pdf_bytes = await asyncio.to_thread(
                slide_import.convert_to_pdf, data, fmt, source_filename
            )
            page_count = slide_import.validate_pdf(pdf_bytes)
            try:
                aoi_candidates = await asyncio.to_thread(
                    slide_aoi.extract_document_aois, pdf_bytes
                )
            except Exception:  # noqa: BLE001
                aoi_candidates = {}

            lesson = await db.get(Lesson, job.lesson_id)
            if lesson is None:
                raise RuntimeError("Bài học không còn tồn tại")
            module = await db.get(CourseModule, lesson.module_id)
            course = await db.get(Course, module.course_id) if module else None
            if course is None:
                raise RuntimeError("Khóa học không còn tồn tại")

            old_asset_id = lesson.pdf_asset_id
            prefix = (
                f"instances/{settings.app_instance_id}/courses/{course.id}/"
                f"lessons/{lesson.id}/{uuid.uuid4().hex[:12]}"
            )
            pdf_asset = await _asset_for_bytes(
                db,
                course=course,
                data=pdf_bytes,
                mime_type="application/pdf",
                object_key=f"{prefix}/source.pdf",
                page_count=page_count,
                source_format=fmt,
            )

            # Thay tài liệu = xóa toàn bộ slide cũ; cascade xóa AOI, lượt xem,
            # layout, gaze thô và metrics của các slide đó.
            await db.execute(
                delete(Slide)
                .where(Slide.lesson_id == lesson.id)
                .execution_options(synchronize_session=False)
            )
            slides = [
                Slide(
                    lesson_id=lesson.id,
                    position=page_no - 1,
                    page_number=page_no,
                    title=f"Slide {page_no}",
                    aoi_suggestions=aoi_candidates.get(page_no, []),
                    index_status="pending",
                )
                for page_no in range(1, page_count + 1)
            ]
            db.add_all(slides)
            lesson.pdf_asset_id = pdf_asset.id
            lesson.updated_at = _now()
            if old_asset_id and old_asset_id != pdf_asset.id:
                removed = await _delete_unreferenced_asset(db, old_asset_id)
                if removed:
                    removed_keys.append(removed)
            touch_course(course)

            job.status = "ready"
            job.payload = {
                **payload,
                "pdf_asset_id": pdf_asset.id,
                "page_count": page_count,
                "converted_format": fmt,
            }
            job.finished_at = _now()
            job.updated_at = _now()
            await db.flush()
            await enqueue_index_lesson(db, lesson.id)
            await db.commit()
            remove_staging = True
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            failed = await db.get(BackgroundJob, job_id)
            if failed is not None:
                failed.error = str(exc)[:1000]
                failed.updated_at = _now()
                if failed.attempts < failed.max_attempts:
                    failed.status = "queued"
                    failed.started_at = None
                    failed.finished_at = None
                else:
                    failed.status = "failed"
                    failed.finished_at = _now()
                    remove_staging = True
                await db.commit()
        finally:
            if remove_staging:
                try:
                    await asyncio.to_thread(media_storage.delete_key, source_key)
                except Exception:  # noqa: BLE001
                    pass

    for key, backend in removed_keys:
        try:
            await asyncio.to_thread(media_storage.delete_key, key)
        except Exception:  # noqa: BLE001
            pass


async def process_pending_slide_imports(limit: int = 1) -> int:
    async with SessionLocal() as db:
        await recover_stale_jobs(
            db,
            kind=IMPORT_KIND,
            stale_seconds=settings.content_worker_stale_seconds,
        )
        jobs = await claim_next_jobs(db, kind=IMPORT_KIND, limit=limit)

    for job in jobs:
        await process_slide_import(job.id)
    return len(jobs)
