"""Slide import jobs, slide rendering and lesson contents."""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import timedelta
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.auth import User
from app.models.course import (
    Course,
    CourseVersionItem,
    LessonVersion,
    LessonVersionSlide,
    Slide,
    SlideVersion,
)
from app.models.media import MediaAsset, SlideDocument, SlideImportJob
from app.schemas.course import SlideAdminOut, SlideOut
from app.services import media_storage, slide_aoi, slide_import
from app.services.content.common import (
    _not_found,
    _now,
    bump_generation,
    get_draft_version,
    get_published_version,
    logger,
)
from app.services.content.lessons import _draft_item
from app.services.content.versions import ensure_draft_lesson_version


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def _asset_for_bytes(
    db: AsyncSession,
    *,
    course: Course,
    data: bytes,
    mime_type: str,
    object_key: str,
    kind: str = "normalized",
    metadata: dict | None = None,
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
        if metadata:
            existing.metadata_ = {**(existing.metadata_ or {}), **metadata}
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
        kind=kind,
        metadata_=metadata or {},
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
) -> SlideImportJob:
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

    draft, item = await _draft_item(db, course, lesson_id, user)
    lesson_version = await ensure_draft_lesson_version(db, item, user)

    # Upload mới thay thế các job còn chờ của cùng lesson version.
    old_jobs = (
        await db.execute(
            select(SlideImportJob).where(
                SlideImportJob.lesson_version_id == lesson_version.id,
                SlideImportJob.status.in_(("queued", "processing")),
            )
        )
    ).scalars().all()
    queued_staging_keys = [
        old.source_object_key for old in old_jobs if old.status == "queued"
    ]
    for old in old_jobs:
        old.status = "cancelled"
        old.finished_at = _now()

    job_id = str(uuid.uuid4())
    suffix = Path(filename or "").suffix.lower() or f".{fmt}"
    staging_key = (
        f"instances/{settings.app_instance_id}/courses/{course.id}/"
        f"lessons/{lesson_id}/imports/{job_id}/upload{suffix}"
    )
    job = SlideImportJob(
        id=job_id,
        course_id=course.id,
        lesson_id=lesson_id,
        lesson_version_id=lesson_version.id,
        created_by=user.id,
        status="queued",
        source_filename=filename or f"slides{suffix}",
        source_mime=slide_import.mime_for_format(fmt),
        source_size=len(data),
        source_sha256=_sha256(data),
        source_object_key=staging_key,
    )
    db.add(job)
    await db.flush()

    try:
        await asyncio.to_thread(
            media_storage.put_bytes, staging_key, data, job.source_mime
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
            logger.warning("Không xoá được staging cũ %s", key)

    bump_generation(draft)
    await db.flush()
    return job


async def get_slide_import_job(
    db: AsyncSession, course: Course, lesson_id: str, job_id: str
) -> SlideImportJob:
    job = await db.get(SlideImportJob, job_id)
    if job is None or job.course_id != course.id or job.lesson_id != lesson_id:
        raise _not_found("Không tìm thấy job tải tài liệu")
    return job


async def process_slide_import(job_id: str) -> None:
    """Worker: convert file staging -> PDF, tạo slide_version cho từng trang."""
    async with SessionLocal() as db:
        job = await db.get(SlideImportJob, job_id)
        if job is None or job.status != "processing":
            return
        source_key = job.source_object_key
        ingest_lesson_version_id: str | None = None

        try:
            data = await asyncio.to_thread(media_storage.get_bytes, source_key)
            fmt = slide_import.detect_format(
                job.source_filename, job.source_mime, data
            )
            pdf_bytes = await asyncio.to_thread(
                slide_import.convert_to_pdf, data, fmt, job.source_filename
            )
            page_count = slide_import.validate_pdf(pdf_bytes)
            try:
                aoi_candidates = await asyncio.to_thread(
                    slide_aoi.extract_document_aois, pdf_bytes
                )
            except Exception:  # noqa: BLE001 - gợi ý lỗi không chặn import
                logger.warning("Không trích xuất được gợi ý vùng AOI", exc_info=True)
                aoi_candidates = {}

            course = await db.get(
                Course,
                job.course_id,
                options=[
                    raiseload(Course.versions),
                    raiseload(Course.enrollments),
                    raiseload(Course.owner),
                    raiseload(Course.creator),
                ],
            )
            user = await db.get(
                User,
                job.created_by,
                options=[raiseload(User.roles)],
            )
            lesson_version = await db.get(
                LessonVersion,
                job.lesson_version_id,
                options=[raiseload(LessonVersion.slides)],
            )
            if course is None or user is None or lesson_version is None:
                raise RuntimeError("Job thiếu course/user/lesson version")

            await db.refresh(job)
            if job.status != "processing":
                return
            if lesson_version.state != "draft":
                raise RuntimeError(
                    "Bản nháp đã được xuất bản trong lúc xử lý; hãy tải lại và thử lại."
                )

            prefix = (
                f"instances/{settings.app_instance_id}/courses/{course.id}/"
                f"lessons/{job.lesson_id}/{uuid.uuid4().hex[:12]}"
            )
            pdf_asset = await _asset_for_bytes(
                db,
                course=course,
                data=pdf_bytes,
                mime_type="application/pdf",
                object_key=f"{prefix}/source.pdf",
                kind="normalized",
                metadata={
                    "page_count": page_count,
                    "source_format": fmt,
                    "converter": "libreoffice",
                },
            )

            # Gỡ membership cũ; slide version/asset cũ vẫn giữ trong lịch sử.
            await db.execute(
                delete(LessonVersionSlide).where(
                    LessonVersionSlide.lesson_version_id == lesson_version.id
                )
            )
            slides = [Slide(lesson_id=job.lesson_id) for _ in range(page_count)]
            db.add_all(slides)
            await db.flush()

            slide_versions = [
                SlideVersion(
                    slide_id=slide.id,
                    revision_no=1,
                    source_pdf_asset_id=pdf_asset.id,
                    source_page=page_no,
                    render_metadata={
                        "converter": "libreoffice",
                        "source_format": fmt,
                        "page_count": page_count,
                        "aoi_layout_version": slide_aoi.AOI_LAYOUT_VERSION,
                        "aoi_candidates": aoi_candidates.get(page_no, []),
                    },
                    created_by=job.created_by,
                )
                for page_no, slide in enumerate(slides, start=1)
            ]
            db.add_all(slide_versions)
            await db.flush()

            db.add_all(
                [
                    LessonVersionSlide(
                        lesson_version_id=lesson_version.id,
                        slide_id=slide.id,
                        slide_version_id=slide_version.id,
                        position=page_no - 1,
                        title=f"Slide {page_no}",
                    )
                    for page_no, (slide, slide_version) in enumerate(
                        zip(slides, slide_versions, strict=True), start=1
                    )
                ]
            )
            await db.flush()

            draft = await get_draft_version(db, course, user, create=False)
            if draft is not None:
                bump_generation(draft)

            job.status = "ready"
            job.pdf_asset_id = pdf_asset.id
            job.page_count = page_count
            job.finished_at = _now()
            await db.commit()
            ingest_lesson_version_id = lesson_version.id
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            failed = await db.get(SlideImportJob, job_id)
            if failed is not None:
                failed.status = "failed"
                failed.error = str(exc)[:1000]
                failed.finished_at = _now()
                await db.commit()
            logger.exception("Slide import job %s thất bại", job_id)
        finally:
            try:
                await asyncio.to_thread(media_storage.delete_key, source_key)
            except Exception:  # noqa: BLE001
                logger.warning("Không xoá được file staging %s", source_key)

    # Index ngay bản nháp để khóa học có thể được xuất bản khi mọi slide đã
    # sẵn sàng. Lỗi index được ghi vào slide_documents và không làm hỏng job
    # import (slide vẫn dùng được, chỉ chặn xuất bản cho tới khi index xong).
    if ingest_lesson_version_id is not None:
        try:
            from app.services import embedding

            await embedding.sync_lesson_version(
                ingest_lesson_version_id, include_draft=True
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Không index được slide cho lesson version %s",
                ingest_lesson_version_id,
                exc_info=True,
            )


async def process_pending_slide_imports(limit: int = 1) -> int:
    """Lấy job queued và xử lý; trả về số job đã nhận."""
    async with SessionLocal() as db:
        stale_before = _now() - timedelta(
            seconds=settings.content_worker_stale_seconds
        )
        await db.execute(
            update(SlideImportJob)
            .where(
                SlideImportJob.status == "processing",
                SlideImportJob.started_at < stale_before,
            )
            .values(status="queued", started_at=None)
        )
        await db.commit()

        jobs = (
            await db.execute(
                select(SlideImportJob)
                .where(SlideImportJob.status == "queued")
                .order_by(SlideImportJob.created_at)
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
        ).scalars().all()
        if not jobs:
            return 0

        job_ids = [job.id for job in jobs]
        for job in jobs:
            job.status = "processing"
            job.started_at = _now()
        await db.commit()

    for job_id in job_ids:
        await process_slide_import(job_id)
    return len(job_ids)


async def list_lesson_slides_admin(
    db: AsyncSession, course: Course, user: User, lesson_id: str
) -> list[SlideAdminOut]:
    draft, item = await _draft_item(db, course, lesson_id, user)
    lesson_version = await ensure_draft_lesson_version(db, item, user)
    rows = (
        await db.execute(
            select(
                LessonVersionSlide,
                SlideVersion,
                MediaAsset,
                SlideDocument,
            )
            .join(
                SlideVersion,
                SlideVersion.id == LessonVersionSlide.slide_version_id,
            )
            .outerjoin(
                MediaAsset,
                MediaAsset.id == SlideVersion.source_pdf_asset_id,
            )
            .outerjoin(
                SlideDocument,
                SlideDocument.slide_version_id
                == LessonVersionSlide.slide_version_id,
            )
            .where(LessonVersionSlide.lesson_version_id == lesson_version.id)
            .order_by(LessonVersionSlide.position)
            .options(
                raiseload(LessonVersionSlide.slide_version),
                raiseload(SlideVersion.source_pdf_asset),
            )
        )
    ).all()
    out: list[SlideAdminOut] = []
    for row, slide_version, asset, document in rows:
        metadata = (asset.metadata_ if asset else {}) or {}
        out.append(
            SlideAdminOut(
                id=row.id,
                order_index=row.position,
                title=row.title or f"Slide {row.position + 1}",
                pdf_url=(
                    media_storage.asset_file_url(asset.id) if asset else None
                ),
                page_number=slide_version.source_page if slide_version else 1,
                page_count=int(metadata.get("page_count") or 1),
                source_format=metadata.get("source_format"),
                embedding_status=document.ingestion_state if document else "none",
                embedding_error=document.ingestion_error if document else None,
                slide_version_id=row.slide_version_id,
                lesson_version_id=row.lesson_version_id,
            )
        )
    return out


def _slide_out(
    row: LessonVersionSlide,
    slide_version: SlideVersion | None,
    asset: MediaAsset | None,
) -> SlideOut:
    metadata = (asset.metadata_ if asset else {}) or {}
    return SlideOut(
        id=row.id,
        title=row.title or f"Slide {row.position + 1}",
        pdf_url=media_storage.asset_file_url(asset.id) if asset else None,
        page_number=slide_version.source_page if slide_version else 1,
        page_count=int(metadata.get("page_count") or 1),
        source_format=metadata.get("source_format"),
        slide_version_id=row.slide_version_id,
        lesson_version_id=row.lesson_version_id,
    )


async def _slide_rows(db: AsyncSession, lesson_version_id: str):
    return (
        await db.execute(
            select(LessonVersionSlide, SlideVersion, MediaAsset)
            .join(
                SlideVersion,
                SlideVersion.id == LessonVersionSlide.slide_version_id,
            )
            .outerjoin(
                MediaAsset,
                MediaAsset.id == SlideVersion.source_pdf_asset_id,
            )
            .where(LessonVersionSlide.lesson_version_id == lesson_version_id)
            .order_by(LessonVersionSlide.position)
            .options(
                raiseload(LessonVersionSlide.slide_version),
                raiseload(SlideVersion.source_pdf_asset),
            )
        )
    ).all()


async def get_lesson_version_contents(
    db: AsyncSession, lesson_version_id: str
) -> list[SlideOut]:
    rows = await _slide_rows(db, lesson_version_id)
    return [_slide_out(row, slide_version, asset) for row, slide_version, asset in rows]


async def get_lesson_contents(
    db: AsyncSession, course: Course, lesson_id: str
) -> list[SlideOut]:
    published = await get_published_version(db, course)
    if published is None:
        raise _not_found("Khóa học chưa được xuất bản")
    item = (
        await db.execute(
            select(CourseVersionItem).where(
                CourseVersionItem.course_version_id == published.id,
                CourseVersionItem.lesson_id == lesson_id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise _not_found("Không tìm thấy bài học trong bản xuất bản")
    rows = await _slide_rows(db, item.lesson_version_id)
    return [_slide_out(row, slide_version, asset) for row, slide_version, asset in rows]
