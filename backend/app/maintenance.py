"""Dọn dẹp dữ liệu hết hạn."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.auth import AuthSession
from app.models.email_otp import EmailOtp
from app.models.gaze import ContentView, CourseVisit, GazeSample, LearningSession
from app.services.embedding_jobs import enqueue_analysis_lesson

# Xoá retention theo batch để transaction ngắn, không giữ lock/WAL trên toàn
# bảng gaze_samples.
GAZE_DELETE_BATCH_SIZE = 10_000


def _utc_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


async def delete_expired_auth_sessions(
    db: AsyncSession, *, now: datetime | None = None
) -> int:
    cutoff = _utc_now(now)
    result = await db.execute(
        delete(AuthSession).where(AuthSession.expires_at < cutoff)
    )
    return result.rowcount or 0


async def _close_open_content_views(
    db: AsyncSession, session_ids, *, cutoff: datetime
) -> int:
    """Đóng các content view còn mở của những session sắp hết hạn.

    Dwell wall time lấy `ended_at` của view/session/visit; nếu view còn mở,
    thời lượng sẽ chạy tới hiện tại mãi. Chốt tại cutoff giữ số liệu ổn định.
    """
    result = await db.execute(
        update(ContentView)
        .where(
            ContentView.session_id.in_(session_ids),
            ContentView.ended_at.is_(None),
        )
        # Không để ended_at sớm hơn started_at (visit cutoff = now - idle).
        .values(ended_at=func.greatest(ContentView.started_at, cutoff))
    )
    return result.rowcount or 0


async def expire_stale_learning_sessions(
    db: AsyncSession, *, now: datetime | None = None
) -> int:
    cutoff = _utc_now(now)
    condition = (
        LearningSession.status == "in_progress",
        LearningSession.expires_at < cutoff,
    )
    session_ids = list(
        (await db.execute(select(LearningSession.id).where(*condition))).scalars()
    )
    if not session_ids:
        return 0
    lesson_ids = list(
        (
            await db.execute(
                select(LearningSession.lesson_id).where(*condition).distinct()
            )
        ).scalars()
    )
    result = await db.execute(
        update(LearningSession)
        .where(*condition)
        .values(status="expired", ended_at=cutoff)
    )
    await _close_open_content_views(db, session_ids, cutoff=cutoff)
    for lesson_id in lesson_ids:
        await enqueue_analysis_lesson(db, lesson_id)
    return result.rowcount or 0


async def expire_stale_course_visits(
    db: AsyncSession, *, now: datetime | None = None, idle_minutes: int = 30
) -> int:
    cutoff = _utc_now(now) - timedelta(minutes=idle_minutes)
    condition = (
        CourseVisit.status == "active",
        CourseVisit.last_seen_at < cutoff,
    )
    visit_ids = list(
        (await db.execute(select(CourseVisit.id).where(*condition))).scalars()
    )
    if not visit_ids:
        return 0
    result = await db.execute(
        update(CourseVisit)
        .where(*condition)
        .values(status="expired", ended_at=cutoff, updated_at=_utc_now(now))
    )

    # Ca hết hạn thì các session in_progress bên trong cũng kết thúc để không
    # còn session "treo" mở gaze. Chỉ chốt ended_at khi chưa có giá trị.
    stale_sessions = (
        LearningSession.course_visit_id.in_(visit_ids),
        LearningSession.status == "in_progress",
    )
    lesson_ids = list(
        (
            await db.execute(
                select(LearningSession.lesson_id)
                .where(*stale_sessions)
                .distinct()
            )
        ).scalars()
    )
    await db.execute(
        update(LearningSession)
        .where(*stale_sessions)
        .values(
            status="expired",
            ended_at=func.coalesce(
                LearningSession.ended_at,
                func.greatest(LearningSession.started_at, cutoff),
            ),
        )
    )
    await _close_open_content_views(
        db,
        select(LearningSession.id).where(
            LearningSession.course_visit_id.in_(visit_ids)
        ),
        cutoff=cutoff,
    )
    for lesson_id in lesson_ids:
        await enqueue_analysis_lesson(db, lesson_id)
    return result.rowcount or 0


async def delete_old_gaze_samples(
    db: AsyncSession,
    *,
    keep_days: int | None = None,
    batch_size: int = GAZE_DELETE_BATCH_SIZE,
) -> int:
    days = settings.gaze_retention_days if keep_days is None else keep_days
    if days <= 0:
        return 0
    batch_size = max(1, batch_size)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    total = 0
    while True:
        result = await db.execute(
            delete(GazeSample)
            .where(
                GazeSample.id.in_(
                    select(GazeSample.id)
                    .where(GazeSample.event_time < cutoff)
                    .limit(batch_size)
                )
            )
            .execution_options(synchronize_session=False)
        )
        deleted = result.rowcount or 0
        await db.commit()
        total += deleted
        if deleted < batch_size:
            break
    return total


async def delete_expired_email_otps(
    db: AsyncSession, *, now: datetime | None = None
) -> int:
    """Xoá challenge OTP đã hết hạn quá 1 ngày (giữ ngắn để điều tra)."""
    cutoff = _utc_now(now) - timedelta(days=1)
    result = await db.execute(
        delete(EmailOtp).where(EmailOtp.expires_at < cutoff)
    )
    return result.rowcount or 0


async def run_maintenance() -> dict[str, int]:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        deleted = await delete_expired_auth_sessions(db, now=now)
        otps_deleted = await delete_expired_email_otps(db, now=now)
        expired = await expire_stale_learning_sessions(db, now=now)
        visits_expired = await expire_stale_course_visits(db, now=now)
        # Chốt các tác vụ nhẹ trước; retention gaze commit từng batch riêng.
        await db.commit()
        gaze_deleted = await delete_old_gaze_samples(db)
        await db.commit()
    return {
        "auth_sessions_deleted": deleted,
        "email_otps_deleted": otps_deleted,
        "learning_sessions_expired": expired,
        "course_visits_expired": visits_expired,
        "gaze_samples_deleted": gaze_deleted,
    }


def main() -> None:
    counts = asyncio.run(run_maintenance())
    print(
        "[maintenance] deleted "
        f"{counts['auth_sessions_deleted']} expired auth session(s)"
    )
    print(
        "[maintenance] deleted "
        f"{counts['email_otps_deleted']} expired email OTP(s)"
    )
    print(
        "[maintenance] expired "
        f"{counts['learning_sessions_expired']} stale learning session(s)"
    )
    print(
        "[maintenance] expired "
        f"{counts['course_visits_expired']} stale course visit(s)"
    )
    print(
        "[maintenance] deleted "
        f"{counts['gaze_samples_deleted']} old gaze sample(s)"
    )


if __name__ == "__main__":
    main()
