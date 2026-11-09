import uuid
from datetime import timedelta

import pytest
from sqlalchemy import delete, func, select

from app.models.embedding_job import EmbeddingJob
from app.services import embedding, embedding_jobs
from tests.conftest import SessionLocal


@pytest.fixture(autouse=True)
async def clean_embedding_jobs():
    """Bảng dùng chung giữa các test; dọn trước và sau mỗi test."""
    async with SessionLocal() as db:
        await db.execute(delete(EmbeddingJob))
        await db.commit()
    yield
    async with SessionLocal() as db:
        await db.execute(delete(EmbeddingJob))
        await db.commit()


async def _count_jobs() -> int:
    async with SessionLocal() as db:
        return (
            await db.execute(select(func.count()).select_from(EmbeddingJob))
        ).scalar_one()


async def _enqueue_course(target_id: str, **kwargs) -> str:
    async with SessionLocal() as db:
        job = await embedding_jobs.enqueue_course_version(db, target_id, **kwargs)
        await db.commit()
        return job.id


async def _enqueue_lesson(target_id: str, **kwargs) -> str:
    async with SessionLocal() as db:
        job = await embedding_jobs.enqueue_lesson_version(db, target_id, **kwargs)
        await db.commit()
        return job.id


async def _claim() -> EmbeddingJob | None:
    async with SessionLocal() as db:
        return await embedding_jobs.claim_next_job(db)


@pytest.mark.asyncio
async def test_enqueue_deduplicates_active_job():
    target_id = str(uuid.uuid4())

    first_id = await _enqueue_course(target_id, include_draft=True, force=True)
    second_id = await _enqueue_course(target_id, include_draft=True, force=True)

    assert second_id == first_id
    assert await _count_jobs() == 1


@pytest.mark.asyncio
async def test_enqueue_different_flags_creates_new_job():
    target_id = str(uuid.uuid4())

    first_id = await _enqueue_course(target_id, include_draft=True, force=True)
    second_id = await _enqueue_course(target_id, include_draft=False, force=True)

    assert second_id != first_id
    assert await _count_jobs() == 2


@pytest.mark.asyncio
async def test_claim_next_job_marks_running_and_increments_attempts():
    target_id = str(uuid.uuid4())
    job_id = await _enqueue_lesson(target_id)

    claimed = await _claim()

    assert claimed is not None
    assert claimed.id == job_id
    assert claimed.status == "running"
    assert claimed.attempts == 1
    assert claimed.started_at is not None

    async with SessionLocal() as db:
        stored = await db.get(EmbeddingJob, job_id)
        assert stored is not None
        assert stored.status == "running"
        assert stored.attempts == 1

    # Không còn job pending để claim.
    assert await _claim() is None


@pytest.mark.asyncio
async def test_process_job_success_course_version(monkeypatch):
    calls: list[tuple[str, bool, bool]] = []

    async def fake_sync(course_version_id, include_draft=False, only_pending=False):
        calls.append((course_version_id, include_draft, only_pending))
        return {"ready": 1, "total": 1}

    monkeypatch.setattr(embedding, "sync_course_version", fake_sync)
    target_id = str(uuid.uuid4())
    job_id = await _enqueue_course(target_id, include_draft=True, force=True)
    assert (await _claim()).id == job_id

    await embedding_jobs.process_job(job_id)

    assert calls == [(target_id, True, True)]
    async with SessionLocal() as db:
        stored = await db.get(EmbeddingJob, job_id)
        assert stored is not None
        assert stored.status == "completed"
        assert stored.error is None
        assert stored.finished_at is not None


@pytest.mark.asyncio
async def test_process_job_success_lesson_version(monkeypatch):
    calls: list[tuple[str, bool, bool]] = []

    async def fake_sync(lesson_version_id, include_draft=False, only_pending=False):
        calls.append((lesson_version_id, include_draft, only_pending))
        return {"ready": 1, "total": 1}

    monkeypatch.setattr(embedding, "sync_lesson_version", fake_sync)
    target_id = str(uuid.uuid4())
    job_id = await _enqueue_lesson(target_id, include_draft=True, force=True)
    assert (await _claim()).id == job_id

    await embedding_jobs.process_job(job_id)

    assert calls == [(target_id, True, True)]
    async with SessionLocal() as db:
        stored = await db.get(EmbeddingJob, job_id)
        assert stored is not None
        assert stored.status == "completed"
        assert stored.finished_at is not None


@pytest.mark.asyncio
async def test_process_job_failure_retries_then_fails(monkeypatch):
    async def failing_sync(*args, **kwargs):
        raise RuntimeError("chatbot ingest lỗi")

    monkeypatch.setattr(embedding, "sync_lesson_version", failing_sync)
    target_id = str(uuid.uuid4())
    job_id = await _enqueue_lesson(target_id, include_draft=True, force=True)

    # attempts 1, 2: còn lượt -> quay lại pending.
    for expected_attempts in (1, 2):
        claimed = await _claim()
        assert claimed is not None
        assert claimed.id == job_id
        assert claimed.attempts == expected_attempts
        await embedding_jobs.process_job(job_id)
        async with SessionLocal() as db:
            stored = await db.get(EmbeddingJob, job_id)
            assert stored is not None
            assert stored.status == "pending"
            assert stored.error == "chatbot ingest lỗi"
            assert stored.finished_at is not None

    # attempts 3 == max_attempts: thất bại hẳn.
    claimed = await _claim()
    assert claimed is not None
    assert claimed.attempts == 3
    await embedding_jobs.process_job(job_id)
    async with SessionLocal() as db:
        stored = await db.get(EmbeddingJob, job_id)
        assert stored is not None
        assert stored.status == "failed"
        assert stored.error == "chatbot ingest lỗi"
        assert stored.finished_at is not None

    assert await _claim() is None


@pytest.mark.asyncio
async def test_recover_stale_running_job_returns_to_pending():
    target_id = str(uuid.uuid4())
    job_id = await _enqueue_lesson(target_id)
    claimed = await _claim()
    assert claimed is not None and claimed.id == job_id

    async with SessionLocal() as db:
        job = await db.get(EmbeddingJob, job_id)
        assert job is not None
        job.started_at = embedding_jobs._now() - timedelta(seconds=3600)
        await db.commit()

    async with SessionLocal() as db:
        recovered = await embedding_jobs.recover_stale_jobs(
            db, stale_seconds=600
        )
    assert recovered == 1

    async with SessionLocal() as db:
        stored = await db.get(EmbeddingJob, job_id)
        assert stored is not None
        assert stored.status == "pending"
        assert stored.error == "stale running job; retrying"
        assert stored.finished_at is None


@pytest.mark.asyncio
async def test_process_pending_jobs_respects_limit(monkeypatch):
    async def fake_sync(*args, **kwargs):
        return {"ready": 1, "total": 1}

    monkeypatch.setattr(embedding, "sync_course_version", fake_sync)
    await _enqueue_course(str(uuid.uuid4()))
    await _enqueue_course(str(uuid.uuid4()))

    assert await embedding_jobs.process_pending_jobs(limit=1) == 1
    assert await embedding_jobs.process_pending_jobs(limit=5) == 1
    assert await embedding_jobs.process_pending_jobs(limit=5) == 0

    async with SessionLocal() as db:
        statuses = (
            await db.execute(select(EmbeddingJob.status))
        ).scalars().all()
    assert statuses == ["completed", "completed"]
