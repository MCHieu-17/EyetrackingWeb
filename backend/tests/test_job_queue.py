"""Tests cho claim/recovery dùng chung của background_jobs."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.session import SessionLocal
from app.models.background_job import BackgroundJob
from app.services import job_queue
from tests.conftest import create_user, seed_course


async def _lesson_id() -> str:
    teacher_id = await create_user(
        email=f"teacher-{uuid.uuid4().hex[:8]}@example.com", role="teacher"
    )
    student_id = await create_user(
        email=f"student-{uuid.uuid4().hex[:8]}@example.com"
    )
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    return ids["lesson_id"]


async def _enqueue(lesson_id: str, *, kind: str, attempts: int = 0) -> str:
    async with SessionLocal() as db:
        job = BackgroundJob(
            lesson_id=lesson_id,
            kind=kind,
            status="queued",
            attempts=attempts,
        )
        db.add(job)
        await db.commit()
        return job.id


@pytest.mark.asyncio
async def test_claim_next_jobs_claims_only_requested_kind():
    lesson_id = await _lesson_id()
    import_id = await _enqueue(lesson_id, kind="import_slides")
    index_id = await _enqueue(lesson_id, kind="index_slides")

    async with SessionLocal() as db:
        claimed = await job_queue.claim_next_jobs(db, kind="index_slides", limit=1)

    assert [job.id for job in claimed] == [index_id]
    assert claimed[0].status == "processing"
    assert claimed[0].attempts == 1
    async with SessionLocal() as db:
        untouched = await db.get(BackgroundJob, import_id)
        assert untouched is not None and untouched.status == "queued"


@pytest.mark.asyncio
async def test_recover_stale_job_requeues_until_max_attempts():
    lesson_id = await _lesson_id()
    job_id = await _enqueue(lesson_id, kind="index_slides", attempts=1)
    async with SessionLocal() as db:
        job = await db.get(BackgroundJob, job_id)
        assert job is not None
        job.status = "processing"
        job.started_at = datetime.now(timezone.utc) - timedelta(hours=1)
        await db.commit()

    async with SessionLocal() as db:
        recovered = await job_queue.recover_stale_jobs(
            db, kind="index_slides", stale_seconds=60
        )
    assert recovered == 1

    async with SessionLocal() as db:
        job = await db.get(BackgroundJob, job_id)
        assert job is not None
        assert job.status == "queued"
        assert job.error == "stale running job; retrying"


@pytest.mark.asyncio
async def test_recover_stale_job_fails_at_max_attempts():
    lesson_id = await _lesson_id()
    job_id = await _enqueue(lesson_id, kind="index_slides", attempts=3)
    async with SessionLocal() as db:
        job = await db.get(BackgroundJob, job_id)
        assert job is not None
        job.status = "processing"
        job.started_at = datetime.now(timezone.utc) - timedelta(hours=1)
        await db.commit()

    async with SessionLocal() as db:
        await job_queue.recover_stale_jobs(db, kind="index_slides", stale_seconds=60)

    async with SessionLocal() as db:
        job = await db.get(BackgroundJob, job_id)
        assert job is not None
        assert job.status == "failed"
        assert "max attempts" in (job.error or "")
