"""Phân tích gaze theo lesson và hàng đợi background job."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.auth import User
from app.models.background_job import BackgroundJob
from app.models.course import Course, CourseModule, Lesson
from app.models.gaze import ContentView, LearningSession
from app.services import metrics
from app.services.access import can_access_course
from app.services.analysis.export import export_lines as export_lines
from app.services.analysis.export import export_visit_lines as export_visit_lines
from app.services.embedding_jobs import ANALYZE_KIND, enqueue_analysis_lesson
from app.services.job_queue import claim_next_jobs, recover_stale_jobs

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def analyze_lesson(lesson_id: str) -> tuple[int, int]:
    """Tính lại toàn bộ lượt xem của một lesson; trả (completed, failed)."""
    completed = failed = 0
    async with SessionLocal() as db:
        view_ids = list(
            (
                await db.execute(
                    select(ContentView.id)
                    .join(
                        LearningSession,
                        LearningSession.id == ContentView.session_id,
                    )
                    .where(LearningSession.lesson_id == lesson_id)
                    .order_by(ContentView.started_at)
                )
            ).scalars()
        )
        for view_id in view_ids:
            try:
                await metrics.analyze_content_view(db, view_id)
                await db.commit()
                completed += 1
            except Exception:  # noqa: BLE001
                await db.rollback()
                failed += 1
                await db.execute(
                    ContentView.__table__.update()
                    .where(ContentView.id == view_id)
                    .values(analysis_status="failed")
                )
                await db.commit()
                logger.exception("Phân tích content view %s thất bại", view_id)
    return completed, failed


async def _claim_job(db: AsyncSession) -> BackgroundJob | None:
    await recover_stale_jobs(
        db, kind=ANALYZE_KIND, stale_seconds=settings.worker_stale_seconds
    )
    jobs = await claim_next_jobs(db, kind=ANALYZE_KIND, limit=1)
    return jobs[0] if jobs else None


async def _process_job(job: BackgroundJob) -> None:
    try:
        _, failed = await analyze_lesson(job.lesson_id)
    except Exception as exc:  # noqa: BLE001
        async with SessionLocal() as db:
            row = await db.get(BackgroundJob, job.id)
            if row is not None:
                row.error = str(exc)[:1000]
                row.updated_at = _now()
                row.finished_at = _now()
                if row.attempts < row.max_attempts:
                    row.status = "queued"
                else:
                    row.status = "failed"
                await db.commit()
        return

    async with SessionLocal() as db:
        row = await db.get(BackgroundJob, job.id)
        # Batch gaze có thể tới sau khi analyze_lesson đã quét danh sách view.
        # Lượt xem còn `pending` cần một job kế tiếp; view `failed` thì không,
        # nên không có vòng lặp vô hạn.
        pending_views = int(
            (
                await db.execute(
                    select(func.count(ContentView.id))
                    .join(
                        LearningSession,
                        LearningSession.id == ContentView.session_id,
                    )
                    .where(
                        LearningSession.lesson_id == job.lesson_id,
                        ContentView.analysis_status == "pending",
                    )
                )
            ).scalar_one()
            or 0
        )
        requeue = (
            row is not None
            and pending_views > 0
            and row.attempts < row.max_attempts
        )
        if row is not None:
            notes: list[str] = []
            if failed:
                notes.append(f"{failed} content view lỗi")
            if pending_views:
                notes.append(f"{pending_views} content view chờ phân tích")
            if requeue:
                row.status = "ready"
                notes.append("đã xếp lại hàng đợi")
            elif failed or pending_views:
                row.status = "failed"
            else:
                row.status = "ready"
            row.error = "; ".join(notes) if notes else None
            row.finished_at = _now()
            row.updated_at = _now()
            # Flush để job hiện tại không còn `processing` khi enqueue job mới
            # (enqueue dedupe theo job đang active của cùng lesson).
            await db.flush()
        if requeue:
            await enqueue_analysis_lesson(db, job.lesson_id)
        await db.commit()


async def execute_pending_runs(limit: int = 10) -> int:
    """Worker entrypoint (giữ tên cũ): claim và xử lý tối đa `limit` job."""
    processed = 0
    for _ in range(limit):
        async with SessionLocal() as db:
            job = await _claim_job(db)
        if job is None:
            break
        await _process_job(job)
        processed += 1
    return processed


async def rebuild_course(
    db: AsyncSession,
    user: User,
    *,
    course_id: str,
    lesson_id: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    algorithm_version: str | None = None,
) -> tuple[int, int, int]:
    del from_time, to_time, algorithm_version
    course = await db.get(Course, course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    if not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")

    lessons_stmt = (
        select(Lesson.id)
        .join(CourseModule, CourseModule.id == Lesson.module_id)
        .where(CourseModule.course_id == course_id, Lesson.kind == "lesson")
    )
    if lesson_id:
        lessons_stmt = lessons_stmt.where(Lesson.id == lesson_id)
    lesson_ids = list((await db.execute(lessons_stmt)).scalars())
    if not lesson_ids:
        return 0, 0, 0

    views = list(
        (
            await db.execute(
                select(ContentView.id)
                .join(LearningSession, LearningSession.id == ContentView.session_id)
                .where(LearningSession.lesson_id.in_(lesson_ids))
            )
        ).scalars()
    )
    if views:
        await db.execute(
            ContentView.__table__.update()
            .where(ContentView.id.in_(views))
            .values(analysis_status="pending")
        )
    for target in lesson_ids:
        await enqueue_analysis_lesson(db, target)
    await db.flush()
    return len(lesson_ids), 0, 0


async def enqueue_lesson_views(db: AsyncSession, lesson_id: str) -> None:
    session_ids = select(LearningSession.id).where(
        LearningSession.lesson_id == lesson_id
    )
    await db.execute(
        ContentView.__table__.update()
        .where(ContentView.session_id.in_(session_ids))
        .values(analysis_status="pending")
    )
    await enqueue_analysis_lesson(db, lesson_id)


async def mark_ui_changed(db: AsyncSession) -> int:
    lesson_ids = list(
        (
            await db.execute(
                select(LearningSession.lesson_id)
                .join(ContentView, ContentView.session_id == LearningSession.id)
                .distinct()
            )
        ).scalars()
    )
    await db.execute(
        ContentView.__table__.update().values(analysis_status="pending")
    )
    for lesson_id in lesson_ids:
        await enqueue_analysis_lesson(db, lesson_id)
    return len(lesson_ids)
