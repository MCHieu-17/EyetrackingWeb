import asyncio
import uuid
from types import SimpleNamespace

import pytest

from app.models.course import Slide
from app.services import embedding
from tests.conftest import SessionLocal, create_user, seed_course, seed_slide


async def _seed_slide(state: str = "pending", error: str | None = None) -> str:
    teacher_id = await create_user(
        email=f"emb-teacher-{uuid.uuid4().hex[:8]}@example.com", role="teacher"
    )
    student_id = await create_user(
        email=f"emb-student-{uuid.uuid4().hex[:8]}@example.com"
    )
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    slide = await seed_slide(
        course_id=ids["course_id"],
        lesson_id=ids["lesson_id"],
        teacher_id=teacher_id,
    )
    async with SessionLocal() as db:
        row = await db.get(Slide, slide["slide_id"])
        assert row is not None
        row.index_status = state
        row.index_error = error
        await db.commit()
    return slide["slide_id"]


@pytest.mark.asyncio
async def test_mark_many_sets_status_and_error():
    slide_id = await _seed_slide("ready")
    async with SessionLocal() as db:
        await embedding._mark_many(db, [slide_id], embedding.PENDING)
    async with SessionLocal() as db:
        slide = await db.get(Slide, slide_id)
        assert slide is not None
        assert slide.index_status == "pending"


@pytest.mark.asyncio
async def test_mark_failed_records_error():
    slide_id = await _seed_slide("pending")
    async with SessionLocal() as db:
        await embedding._mark_many(db, [slide_id], embedding.FAILED, "batch failed")
    async with SessionLocal() as db:
        slide = await db.get(Slide, slide_id)
        assert slide is not None
        assert slide.index_status == "failed"
        assert slide.index_error == "batch failed"


@pytest.mark.asyncio
async def test_status_counts_treat_none_as_pending():
    lesson_id = None
    teacher_id = await create_user(
        email=f"emb2-teacher-{uuid.uuid4().hex[:8]}@example.com", role="teacher"
    )
    student_id = await create_user(
        email=f"emb2-student-{uuid.uuid4().hex[:8]}@example.com"
    )
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    lesson_id = ids["lesson_id"]
    await seed_slide(
        course_id=ids["course_id"], lesson_id=lesson_id, teacher_id=teacher_id
    )
    async with SessionLocal() as db:
        counts = await embedding._status_counts(db, lesson_id)
    assert counts == {"ready": 1, "failed": 0, "pending": 0, "total": 1}


async def _seed_lesson_slides(count: int = 1) -> tuple[str, list[str]]:
    teacher_id = await create_user(
        email=f"emb-mixed-teacher-{uuid.uuid4().hex[:8]}@example.com", role="teacher"
    )
    student_id = await create_user(
        email=f"emb-mixed-student-{uuid.uuid4().hex[:8]}@example.com"
    )
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    slide_ids = []
    for position in range(count):
        slide = await seed_slide(
            course_id=ids["course_id"],
            lesson_id=ids["lesson_id"],
            teacher_id=teacher_id,
            position=position,
        )
        slide_ids.append(slide["slide_id"])
    return ids["lesson_id"], slide_ids


async def _set_statuses(slide_ids: list[str], status: str) -> None:
    async with SessionLocal() as db:
        await embedding._mark_many(db, slide_ids, status)


@pytest.mark.asyncio
async def test_single_flight_is_per_lesson():
    started = asyncio.Event()
    release = asyncio.Event()

    async def hold_lesson_a():
        async with embedding._single_flight("lesson:a") as acquired:
            assert acquired is True
            started.set()
            await release.wait()

    task = asyncio.create_task(hold_lesson_a())
    await started.wait()

    async with embedding._single_flight("lesson:a") as acquired:
        assert acquired is False
    async with embedding._single_flight("lesson:b") as acquired:
        assert acquired is True

    release.set()
    await task


@pytest.mark.asyncio
async def test_sync_lesson_single_flight_skips_duplicate(monkeypatch):
    lesson_a, _ = await _seed_lesson_slides()
    lesson_b, _ = await _seed_lesson_slides()
    started_a = asyncio.Event()
    release_a = asyncio.Event()
    started_b = asyncio.Event()
    calls: list[str] = []

    async def fake_sync(session, *, lesson_id, all_slide_ids, only_pending):
        calls.append(lesson_id)
        if lesson_id == lesson_a:
            started_a.set()
            await release_a.wait()
        else:
            started_b.set()
        return {
            "ready": 0,
            "failed": 0,
            "pending": len(all_slide_ids),
            "total": len(all_slide_ids),
        }

    monkeypatch.setattr(embedding, "_sync", fake_sync)
    monkeypatch.setattr(embedding, "settings", SimpleNamespace(chatbot_ready=True))

    first = asyncio.create_task(embedding.sync_lesson(lesson_a))
    await started_a.wait()

    duplicate = await asyncio.wait_for(
        embedding.sync_lesson(lesson_a), timeout=2
    )
    assert calls == [lesson_a]
    assert duplicate["total"] == 1

    other = asyncio.create_task(embedding.sync_lesson(lesson_b))
    await asyncio.wait_for(started_b.wait(), timeout=2)
    assert set(calls) == {lesson_a, lesson_b}

    release_a.set()
    await asyncio.wait_for(first, timeout=2)
    other_result = await asyncio.wait_for(other, timeout=2)
    assert other_result["total"] == 1


@pytest.mark.asyncio
async def test_sync_transport_failure_preserves_mixed_outcomes(monkeypatch):
    lesson_id, slide_ids = await _seed_lesson_slides(3)
    await _set_statuses(slide_ids, embedding.PENDING)
    calls: list[list[str]] = []

    async def failing_call(payload):
        calls.append(list(payload["slide_ids"]))
        async with SessionLocal() as db:
            await embedding._mark_many(db, [slide_ids[0]], embedding.READY)
            await embedding._mark_many(
                db,
                [slide_ids[1]],
                embedding.FAILED,
                "VLM tạm thời không khả dụng",
            )
        raise RuntimeError("transport")

    monkeypatch.setattr(embedding, "_call", failing_call)
    async with SessionLocal() as db:
        counts = await embedding._sync(
            db,
            lesson_id=lesson_id,
            all_slide_ids=slide_ids,
            only_pending=True,
        )

    assert counts == {"ready": 1, "failed": 2, "pending": 0, "total": 3}
    async with SessionLocal() as db:
        first = await db.get(Slide, slide_ids[0])
        second = await db.get(Slide, slide_ids[1])
        third = await db.get(Slide, slide_ids[2])
        assert first is not None and first.index_status == "ready"
        assert first.index_error is None
        assert second is not None and second.index_status == "failed"
        assert second.index_error == "VLM tạm thời không khả dụng"
        assert third is not None and third.index_status == "failed"
        assert third.index_error == "transport"

    async def retry_call(payload):
        calls.append(list(payload["slide_ids"]))
        async with SessionLocal() as db:
            await embedding._mark_many(db, payload["slide_ids"], embedding.READY)
        return {
            "processed": len(payload["slide_ids"]),
            "failed": 0,
            "errors": [],
        }

    monkeypatch.setattr(embedding, "_call", retry_call)
    async with SessionLocal() as db:
        counts = await embedding._sync(
            db,
            lesson_id=lesson_id,
            all_slide_ids=slide_ids,
            only_pending=True,
        )

    assert counts == {"ready": 3, "failed": 0, "pending": 0, "total": 3}
    assert calls[1] == slide_ids[1:]


@pytest.mark.asyncio
async def test_sync_mixed_response_does_not_fail_processed_slides(monkeypatch):
    lesson_id, slide_ids = await _seed_lesson_slides(2)
    await _set_statuses(slide_ids, embedding.PENDING)

    async def mixed_call(payload):
        async with SessionLocal() as db:
            await embedding._mark_many(db, [slide_ids[0]], embedding.READY)
            await embedding._mark_many(
                db, [slide_ids[1]], embedding.FAILED, "VLM lỗi"
            )
        return {
            "processed": 1,
            "failed": 1,
            "errors": [f"{slide_ids[1]}: VLM lỗi"],
        }

    monkeypatch.setattr(embedding, "_call", mixed_call)
    async with SessionLocal() as db:
        counts = await embedding._sync(
            db,
            lesson_id=lesson_id,
            all_slide_ids=slide_ids,
            only_pending=True,
        )

    assert counts == {"ready": 1, "failed": 1, "pending": 0, "total": 2}
    async with SessionLocal() as db:
        first = await db.get(Slide, slide_ids[0])
        assert first is not None
        assert first.index_status == "ready"
        assert first.index_error is None
