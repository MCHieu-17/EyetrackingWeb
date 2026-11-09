import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.maintenance import (
    delete_expired_auth_sessions,
    expire_stale_learning_sessions,
)
from app.models.auth import AuthSession
from app.models.gaze import LearningSession
from tests.conftest import SessionLocal, create_user, seed_course


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_delete_expired_auth_sessions_removes_expired_and_revoked_expired():
    user_id = await create_user(
        email=f"maint-auth-{uuid.uuid4().hex[:8]}@example.com"
    )
    now = _now()
    expired_id = str(uuid.uuid4())
    revoked_expired_id = str(uuid.uuid4())
    active_id = str(uuid.uuid4())
    session_ids = [expired_id, revoked_expired_id, active_id]

    async with SessionLocal() as db:
        db.add_all(
            [
                AuthSession(
                    id=expired_id,
                    user_id=user_id,
                    refresh_token_hash=f"hash-{uuid.uuid4().hex}",
                    expires_at=now - timedelta(hours=1),
                ),
                AuthSession(
                    id=revoked_expired_id,
                    user_id=user_id,
                    refresh_token_hash=f"hash-{uuid.uuid4().hex}",
                    expires_at=now - timedelta(hours=2),
                    revoked_at=now - timedelta(hours=1),
                ),
                AuthSession(
                    id=active_id,
                    user_id=user_id,
                    refresh_token_hash=f"hash-{uuid.uuid4().hex}",
                    expires_at=now + timedelta(hours=1),
                ),
            ]
        )
        await db.commit()

    try:
        async with SessionLocal() as db:
            deleted = await delete_expired_auth_sessions(db, now=now)
            await db.commit()

        assert deleted == 2
        async with SessionLocal() as db:
            remaining = (
                (
                    await db.execute(
                        select(AuthSession.id).where(
                            AuthSession.id.in_(session_ids)
                        )
                    )
                )
                .scalars()
                .all()
            )
        assert remaining == [active_id]
    finally:
        async with SessionLocal() as db:
            await db.execute(
                delete(AuthSession).where(AuthSession.id.in_(session_ids))
            )
            await db.commit()


@pytest.mark.asyncio
async def test_expire_stale_learning_sessions_only_updates_past_due():
    teacher_id = await create_user(
        email=f"maint-teacher-{uuid.uuid4().hex[:8]}@example.com",
        role="teacher",
    )
    student_id = await create_user(
        email=f"maint-student-{uuid.uuid4().hex[:8]}@example.com"
    )
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    now = _now()
    stale_id = str(uuid.uuid4())
    future_id = str(uuid.uuid4())
    session_ids = [stale_id, future_id]

    async with SessionLocal() as db:
        db.add_all(
            [
                LearningSession(
                    id=stale_id,
                    enrollment_id=ids["enrollment_id"],
                    course_version_item_id=ids["item_id"],
                    pipeline_version="test",
                    status="in_progress",
                    expires_at=now - timedelta(minutes=5),
                ),
                LearningSession(
                    id=future_id,
                    enrollment_id=ids["enrollment_id"],
                    course_version_item_id=ids["item_id"],
                    pipeline_version="test",
                    status="in_progress",
                    expires_at=now + timedelta(hours=1),
                ),
            ]
        )
        await db.commit()

    try:
        async with SessionLocal() as db:
            expired = await expire_stale_learning_sessions(db, now=now)
            await db.commit()

        assert expired == 1
        async with SessionLocal() as db:
            stale = await db.get(LearningSession, stale_id)
            future = await db.get(LearningSession, future_id)

        assert stale is not None
        assert stale.status == "expired"
        assert stale.ended_at == now
        assert future is not None
        assert future.status == "in_progress"
        assert future.ended_at is None
    finally:
        async with SessionLocal() as db:
            await db.execute(
                delete(LearningSession).where(LearningSession.id.in_(session_ids))
            )
            await db.commit()
