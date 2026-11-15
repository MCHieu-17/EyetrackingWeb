import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.maintenance import (
    delete_expired_auth_sessions,
    delete_old_gaze_samples,
    expire_stale_learning_sessions,
)
from app.models.auth import AuthSession
from app.models.gaze import GazeSample, LearningSession
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
                    lesson_id=ids["lesson_id"],
                    pipeline_version="test",
                    status="in_progress",
                    expires_at=now - timedelta(minutes=5),
                ),
                LearningSession(
                    id=future_id,
                    enrollment_id=ids["enrollment_id"],
                    lesson_id=ids["lesson_id"],
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
        assert stale is not None and stale.status == "expired"
        assert future is not None and future.status == "in_progress"
    finally:
        async with SessionLocal() as db:
            await db.execute(
                delete(LearningSession).where(LearningSession.id.in_(session_ids))
            )
            await db.commit()


@pytest.mark.asyncio
async def test_delete_old_gaze_samples():
    teacher_id = await create_user(
        email=f"maint2-teacher-{uuid.uuid4().hex[:8]}@example.com",
        role="teacher",
    )
    student_id = await create_user(
        email=f"maint2-student-{uuid.uuid4().hex[:8]}@example.com"
    )
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    now = _now()

    from app.models.gaze import ContentView

    async with SessionLocal() as db:
        session = LearningSession(
            enrollment_id=ids["enrollment_id"],
            lesson_id=ids["lesson_id"],
            status="completed",
            expires_at=now + timedelta(hours=1),
        )
        db.add(session)
        await db.flush()
        view = ContentView(
            session_id=session.id,
            surface="quiz",
            sequence_no=0,
        )
        db.add(view)
        await db.flush()
        old_id = uuid.uuid4()
        new_id = uuid.uuid4()
        db.add_all(
            [
                GazeSample(
                    content_view_id=view.id,
                    client_batch_id=old_id,
                    sequence=0,
                    event_time=now - timedelta(days=400),
                    viewport_x=0.5,
                    viewport_y=0.5,
                    status="ok",
                ),
                GazeSample(
                    content_view_id=view.id,
                    client_batch_id=new_id,
                    sequence=1,
                    event_time=now,
                    viewport_x=0.5,
                    viewport_y=0.5,
                    status="ok",
                ),
            ]
        )
        await db.commit()
        view_id = view.id

    try:
        async with SessionLocal() as db:
            deleted = await delete_old_gaze_samples(db, keep_days=180)
            await db.commit()
        assert deleted == 1
        async with SessionLocal() as db:
            remaining = (
                await db.execute(
                    select(GazeSample.client_batch_id).where(
                        GazeSample.content_view_id == view_id
                    )
                )
            ).scalars().all()
        assert remaining == [str(new_id)]
    finally:
        async with SessionLocal() as db:
            await db.execute(delete(ContentView).where(ContentView.id == view_id))
            await db.commit()
