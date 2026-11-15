import uuid

import pytest
from sqlalchemy import delete, func, select, update

from app.models.background_job import BackgroundJob
from app.services import embedding, embedding_jobs
from tests.conftest import SessionLocal, create_user, seed_course


@pytest.fixture(autouse=True)
async def clean_background_jobs():
    async with SessionLocal() as db:
        await db.execute(delete(BackgroundJob))
        await db.commit()
    yield
    async with SessionLocal() as db:
        await db.execute(delete(BackgroundJob))
        await db.commit()


async def _seed_lesson() -> str:
    teacher_id = await create_user(
        email=f"jobs-teacher-{uuid.uuid4().hex[:8]}@example.com", role="teacher"
    )
    student_id = await create_user(
        email=f"jobs-student-{uuid.uuid4().hex[:8]}@example.com"
    )
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    return ids["lesson_id"]


async def _count_jobs() -> int:
    async with SessionLocal() as db:
        return (
            await db.execute(select(func.count()).select_from(BackgroundJob))
        ).scalar_one()


async def _enqueue(lesson_id: str) -> str:
    async with SessionLocal() as db:
        job = await embedding_jobs.enqueue_index_lesson(db, lesson_id)
        await db.commit()
        return job.id


async def _claim() -> BackgroundJob | None:
    async with SessionLocal() as db:
        return await embedding_jobs.claim_next_job(db)


@pytest.mark.asyncio
async def test_enqueue_deduplicates_active_job():
    lesson_id = await _seed_lesson()
    first_id = await _enqueue(lesson_id)
    second_id = await _enqueue(lesson_id)
    assert second_id == first_id
    assert await _count_jobs() == 1


@pytest.mark.asyncio
async def test_claim_next_job_marks_processing_and_increments_attempts():
    lesson_id = await _seed_lesson()
    job_id = await _enqueue(lesson_id)
    claimed = await _claim()
    assert claimed is not None
    assert claimed.id == job_id
    assert claimed.status == "processing"
    assert claimed.attempts == 1
    assert claimed.started_at is not None
    assert await _claim() is None


@pytest.mark.asyncio
async def test_process_job_success(monkeypatch):
    calls: list[tuple[str, bool]] = []

    async def fake_sync(lesson_id, only_pending=True):
        calls.append((lesson_id, only_pending))
        return {"ready": 1, "total": 1}

    monkeypatch.setattr(embedding, "sync_lesson", fake_sync)
    lesson_id = await _seed_lesson()
    job_id = await _enqueue(lesson_id)
    assert (await _claim()).id == job_id
    await embedding_jobs.process_job(job_id)
    assert calls == [(lesson_id, True)]
    async with SessionLocal() as db:
        stored = await db.get(BackgroundJob, job_id)
        assert stored is not None
        assert stored.status == "ready"
        assert stored.error is None
        assert stored.finished_at is not None


@pytest.mark.asyncio
async def test_process_job_failure_retries_then_fails(monkeypatch):
    async def failing_sync(*args, **kwargs):
        raise RuntimeError("chatbot ingest lỗi")

    monkeypatch.setattr(embedding, "sync_lesson", failing_sync)
    lesson_id = await _seed_lesson()
    job_id = await _enqueue(lesson_id)

    for expected_attempts in (1, 2):
        claimed = await _claim()
        assert claimed is not None and claimed.id == job_id
        assert claimed.attempts == expected_attempts
        await embedding_jobs.process_job(job_id)
        async with SessionLocal() as db:
            stored = await db.get(BackgroundJob, job_id)
            assert stored is not None
            assert stored.status == "queued"
            assert stored.error == "chatbot ingest lỗi"

    claimed = await _claim()
    assert claimed is not None and claimed.attempts == 3
    await embedding_jobs.process_job(job_id)
    async with SessionLocal() as db:
        stored = await db.get(BackgroundJob, job_id)
        assert stored is not None
        assert stored.status == "failed"
    assert await _claim() is None


@pytest.mark.asyncio
async def test_recover_stale_processing_job_returns_to_queue():
    lesson_id = await _seed_lesson()
    job_id = await _enqueue(lesson_id)
    claimed = await _claim()
    assert claimed is not None and claimed.id == job_id
    async with SessionLocal() as db:
        await db.execute(
            update(BackgroundJob)
            .where(BackgroundJob.id == job_id)
            .values(started_at=embedding_jobs._now().replace(year=2000))
        )
        await db.commit()
    async with SessionLocal() as db:
        recovered = await embedding_jobs.recover_stale_jobs(db, stale_seconds=600)
    assert recovered == 1
    async with SessionLocal() as db:
        stored = await db.get(BackgroundJob, job_id)
        assert stored is not None
        assert stored.status == "queued"
