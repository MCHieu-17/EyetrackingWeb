"""Dọn dẹp dữ liệu hết hạn."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.auth import AuthSession
from app.models.gaze import CourseVisit, GazeSample, LearningSession
from app.services.embedding_jobs import enqueue_analysis_lesson


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
    condition = or_(
        AuthSession.expires_at < cutoff,
        and_(
            AuthSession.revoked_at.is_not(None),
            AuthSession.expires_at < cutoff,
        ),
    )
    result = await db.execute(delete(AuthSession).where(condition))
    return result.rowcount or 0


async def expire_stale_learning_sessions(
    db: AsyncSession, *, now: datetime | None = None
) -> int:
    cutoff = _utc_now(now)
    condition = (
        LearningSession.status == "in_progress",
        LearningSession.expires_at < cutoff,
    )
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
    for lesson_id in lesson_ids:
        await enqueue_analysis_lesson(db, lesson_id)
    return result.rowcount or 0


async def expire_stale_course_visits(
    db: AsyncSession, *, now: datetime | None = None, idle_minutes: int = 30
) -> int:
    cutoff = _utc_now(now) - timedelta(minutes=idle_minutes)
    result = await db.execute(
        update(CourseVisit)
        .where(
            CourseVisit.status == "active",
            CourseVisit.last_seen_at < cutoff,
        )
        .values(status="expired", ended_at=cutoff, updated_at=_utc_now(now))
    )
    return result.rowcount or 0


async def delete_old_gaze_samples(
    db: AsyncSession, *, keep_days: int | None = None
) -> int:
    days = settings.gaze_retention_days if keep_days is None else keep_days
    if days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        delete(GazeSample).where(GazeSample.event_time < cutoff)
    )
    return result.rowcount or 0


async def run_maintenance() -> dict[str, int]:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        deleted = await delete_expired_auth_sessions(db, now=now)
        expired = await expire_stale_learning_sessions(db, now=now)
        visits_expired = await expire_stale_course_visits(db, now=now)
        gaze_deleted = await delete_old_gaze_samples(db)
        await db.commit()
    return {
        "auth_sessions_deleted": deleted,
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
