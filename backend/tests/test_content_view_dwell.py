"""Dwell wall time của content view và bộ lọc lượt xem ngắn.

Mặc định Replay/Tổng hợp trả mọi lượt xem, kể cả lượt không có sample gaze
hoặc ngắn hơn `CONTENT_VIEW_MIN_DWELL_MS`; ngưỡng chỉ dùng để phân loại
`counted` và làm bộ lọc tùy chọn.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.maintenance import (
    expire_stale_course_visits,
    expire_stale_learning_sessions,
)
from app.models.background_job import BackgroundJob
from app.models.gaze import ContentView, CourseVisit, LearningSession
from app.services import analysis
from tests.conftest import create_user, login, seed_course, seed_slide

LONG_DWELL_MS = 90_000
SHORT_DWELL_MS = 250


async def _seed_dwell_visit() -> dict:
    teacher_email = f"dwell-t-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"dwell-s-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    slide = await seed_slide(
        course_id=ids["course_id"],
        lesson_id=ids["lesson_id"],
        teacher_id=teacher_id,
    )

    now = datetime.now(timezone.utc)
    visit_start = now - timedelta(minutes=20)
    visit_end = now - timedelta(minutes=10)

    async with SessionLocal() as db:
        visit = CourseVisit(
            enrollment_id=ids["enrollment_id"],
            started_at=visit_start,
            last_seen_at=visit_end,
            status="ended",
            ended_at=visit_end,
        )
        db.add(visit)
        await db.flush()
        session = LearningSession(
            enrollment_id=ids["enrollment_id"],
            lesson_id=ids["lesson_id"],
            course_visit_id=visit.id,
            status="completed",
            started_at=visit_start,
            ended_at=visit_end,
            expires_at=now + timedelta(hours=1),
        )
        db.add(session)
        await db.flush()

        # Lượt dài nhưng không có sample gaze: vẫn phải xuất hiện.
        long_view = ContentView(
            session_id=session.id,
            slide_id=slide["slide_id"],
            surface="lesson",
            sequence_no=0,
            started_at=visit_start,
            ended_at=visit_start + timedelta(milliseconds=LONG_DWELL_MS),
            gaze_count=10,
            on_slide_gaze_count=8,
            tracked_duration_ms=4500,
            fixation_count=3,
        )
        # Lượt ngắn hơn ngưỡng 1000ms.
        short_view = ContentView(
            session_id=session.id,
            slide_id=slide["slide_id"],
            surface="lesson",
            sequence_no=1,
            started_at=visit_start + timedelta(milliseconds=LONG_DWELL_MS),
            ended_at=visit_start
            + timedelta(milliseconds=LONG_DWELL_MS + SHORT_DWELL_MS),
            gaze_count=2,
            on_slide_gaze_count=1,
            tracked_duration_ms=120,
            fixation_count=0,
        )
        db.add_all([long_view, short_view])
        await db.commit()

    return {
        "teacher_email": teacher_email,
        "course_id": ids["course_id"],
        "lesson_id": ids["lesson_id"],
        "enrollment_id": ids["enrollment_id"],
        "visit_id": visit.id,
        "long_view_id": long_view.id,
        "short_view_id": short_view.id,
    }


@pytest.mark.asyncio
async def test_replay_includes_zero_sample_and_short_views_by_default(client):
    data = await _seed_dwell_visit()
    token = await login(client, data["teacher_email"])
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        f"/teacher/visits/{data['visit_id']}/replay", headers=headers
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    views = {item["sequenceNo"]: item for item in payload["views"]}
    assert set(views) == {0, 1}

    long_view = views[0]
    assert long_view["sampleCount"] == 0
    assert long_view["dwellMs"] == LONG_DWELL_MS
    assert long_view["counted"] is True

    short_view = views[1]
    assert short_view["sampleCount"] == 0
    assert short_view["dwellMs"] == SHORT_DWELL_MS
    assert short_view["counted"] is False

    visit = payload["visit"]
    assert visit["contentViewCount"] == 2
    assert visit["shortViewCount"] == 1
    assert visit["minDwellMs"] == 1000


@pytest.mark.asyncio
async def test_replay_include_short_false_hides_only_short_views(client):
    data = await _seed_dwell_visit()
    token = await login(client, data["teacher_email"])
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        f"/teacher/visits/{data['visit_id']}/replay",
        params={"includeShort": "false"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert [item["sequenceNo"] for item in payload["views"]] == [0]
    visit = payload["visit"]
    assert visit["contentViewCount"] == 1
    assert visit["shortViewCount"] == 1
    assert visit["trackedDurationMs"] == 4500


@pytest.mark.asyncio
async def test_visit_summary_include_short_is_consistent_with_replay(client):
    data = await _seed_dwell_visit()
    token = await login(client, data["teacher_email"])
    headers = {"Authorization": f"Bearer {token}"}
    url = f"/teacher/visits/{data['visit_id']}/summary"

    response = await client.get(url, headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["lessonSessionCount"] == 1
    assert payload["contentViewCount"] == 2
    assert payload["gazeCount"] == 12
    assert payload["trackedDurationMs"] == 4620
    assert payload["shortViewCount"] == 1
    assert payload["minDwellMs"] == 1000

    response = await client.get(
        url, params={"includeShort": "false"}, headers=headers
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["lessonSessionCount"] == 1
    assert payload["contentViewCount"] == 1
    assert payload["gazeCount"] == 10
    assert payload["trackedDurationMs"] == 4500
    assert payload["shortViewCount"] == 1


@pytest.mark.asyncio
async def test_course_visit_list_sums_only_counted_views_when_filtered(client):
    data = await _seed_dwell_visit()
    token = await login(client, data["teacher_email"])
    headers = {"Authorization": f"Bearer {token}"}
    url = f"/teacher/courses/{data['course_id']}/visits"

    response = await client.get(url, headers=headers)
    assert response.status_code == 200, response.text
    row = response.json()[0]
    assert row["gazeCount"] == 12
    assert row["trackedDurationMs"] == 4620

    response = await client.get(
        url, params={"includeShort": "false"}, headers=headers
    )
    assert response.status_code == 200, response.text
    row = response.json()[0]
    assert row["gazeCount"] == 10
    assert row["trackedDurationMs"] == 4500


@pytest.mark.asyncio
async def test_expire_stale_learning_session_closes_open_views():
    now = datetime.now(timezone.utc)
    teacher_id = await create_user(
        email=f"dwell-mt-{uuid.uuid4().hex[:8]}@example.com", role="teacher"
    )
    student_id = await create_user(
        email=f"dwell-ms-{uuid.uuid4().hex[:8]}@example.com"
    )
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)

    async with SessionLocal() as db:
        session = LearningSession(
            enrollment_id=ids["enrollment_id"],
            lesson_id=ids["lesson_id"],
            status="in_progress",
            started_at=now - timedelta(minutes=30),
            expires_at=now - timedelta(minutes=5),
        )
        db.add(session)
        await db.flush()
        open_view = ContentView(
            session_id=session.id,
            surface="quiz",
            sequence_no=0,
            started_at=now - timedelta(minutes=20),
            ended_at=None,
        )
        closed_view = ContentView(
            session_id=session.id,
            surface="quiz",
            sequence_no=1,
            started_at=now - timedelta(minutes=10),
            ended_at=now - timedelta(minutes=9),
        )
        db.add_all([open_view, closed_view])
        await db.commit()
        open_view_id = open_view.id
        closed_view_id = closed_view.id
        session_id = session.id

    try:
        async with SessionLocal() as db:
            expired = await expire_stale_learning_sessions(db, now=now)
            await db.commit()
        assert expired == 1

        async with SessionLocal() as db:
            stored = await db.get(ContentView, open_view_id)
            untouched = await db.get(ContentView, closed_view_id)
        assert stored is not None and stored.ended_at is not None
        assert stored.ended_at == now
        # View đã đóng trước đó không bị ghi đè.
        assert untouched is not None
        assert untouched.ended_at == now - timedelta(minutes=9)
    finally:
        async with SessionLocal() as db:
            await db.execute(
                delete(LearningSession).where(LearningSession.id == session_id)
            )
            await db.commit()


@pytest.mark.asyncio
async def test_expire_stale_course_visit_closes_sessions_and_views():
    now = datetime.now(timezone.utc)
    teacher_id = await create_user(
        email=f"dwell-vt-{uuid.uuid4().hex[:8]}@example.com", role="teacher"
    )
    student_id = await create_user(
        email=f"dwell-vs-{uuid.uuid4().hex[:8]}@example.com"
    )
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)

    async with SessionLocal() as db:
        visit = CourseVisit(
            enrollment_id=ids["enrollment_id"],
            started_at=now - timedelta(hours=2),
            last_seen_at=now - timedelta(minutes=60),
            status="active",
        )
        db.add(visit)
        await db.flush()
        session = LearningSession(
            enrollment_id=ids["enrollment_id"],
            lesson_id=ids["lesson_id"],
            course_visit_id=visit.id,
            status="in_progress",
            started_at=now - timedelta(minutes=90),
            expires_at=now + timedelta(hours=1),
        )
        db.add(session)
        await db.flush()
        view = ContentView(
            session_id=session.id,
            surface="quiz",
            sequence_no=0,
            started_at=now - timedelta(minutes=80),
            ended_at=None,
        )
        # View mở sau cutoff (now - 30 phút) không được nhận ended_at < started_at.
        late_view = ContentView(
            session_id=session.id,
            surface="quiz",
            sequence_no=1,
            started_at=now - timedelta(minutes=10),
            ended_at=None,
        )
        db.add_all([view, late_view])
        await db.commit()
        visit_id = visit.id
        session_id = session.id
        view_id = view.id
        late_view_id = late_view.id

    try:
        async with SessionLocal() as db:
            expired = await expire_stale_course_visits(db, now=now)
            await db.commit()
        assert expired == 1

        async with SessionLocal() as db:
            stored_visit = await db.get(CourseVisit, visit_id)
            stored_session = await db.get(LearningSession, session_id)
            stored_view = await db.get(ContentView, view_id)
            stored_late = await db.get(ContentView, late_view_id)
        assert stored_visit is not None and stored_visit.status == "expired"
        assert stored_session is not None and stored_session.status == "expired"
        assert stored_session.ended_at is not None
        assert stored_view is not None and stored_view.ended_at is not None
        assert stored_view.ended_at == stored_visit.ended_at
        assert stored_late is not None
        assert stored_late.ended_at == stored_late.started_at
    finally:
        async with SessionLocal() as db:
            await db.execute(delete(CourseVisit).where(CourseVisit.id == visit_id))
            await db.commit()


@pytest.mark.asyncio
async def test_analyze_job_requeues_when_pending_view_remains(monkeypatch):
    teacher_id = await create_user(
        email=f"dwell-jt-{uuid.uuid4().hex[:8]}@example.com", role="teacher"
    )
    student_id = await create_user(
        email=f"dwell-js-{uuid.uuid4().hex[:8]}@example.com"
    )
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)

    async with SessionLocal() as db:
        await db.execute(
            delete(BackgroundJob).where(BackgroundJob.lesson_id == ids["lesson_id"])
        )
        session = LearningSession(
            enrollment_id=ids["enrollment_id"],
            lesson_id=ids["lesson_id"],
            status="completed",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(session)
        await db.flush()
        view = ContentView(
            session_id=session.id,
            surface="quiz",
            sequence_no=0,
            analysis_status="pending",
        )
        db.add(view)
        job = BackgroundJob(
            lesson_id=ids["lesson_id"],
            kind="analyze_lesson",
            status="processing",
            attempts=1,
            max_attempts=3,
        )
        db.add(job)
        await db.commit()
        job_id = job.id
        view_id = view.id

    async def fake_analyze(lesson_id: str) -> tuple[int, int]:
        # Mô phỏng view còn pending sau khi job kết thúc (batch tới muộn).
        assert lesson_id == ids["lesson_id"]
        return (0, 0)

    monkeypatch.setattr(analysis, "analyze_lesson", fake_analyze)

    async with SessionLocal() as db:
        claimed = await db.get(BackgroundJob, job_id)
    assert claimed is not None
    await analysis._process_job(claimed)

    async with SessionLocal() as db:
        stored = await db.get(BackgroundJob, job_id)
        queued = (
            await db.execute(
                select(BackgroundJob).where(
                    BackgroundJob.lesson_id == ids["lesson_id"],
                    BackgroundJob.status == "queued",
                )
            )
        ).scalars().all()
        stored_view = await db.get(ContentView, view_id)
        await db.execute(
            delete(BackgroundJob).where(BackgroundJob.lesson_id == ids["lesson_id"])
        )
        await db.commit()

    assert stored is not None and stored.status == "ready"
    assert len(queued) == 1
    assert queued[0].id != job_id
    assert stored_view is not None and stored_view.analysis_status == "pending"


@pytest.mark.asyncio
async def test_analyze_job_does_not_requeue_after_max_attempts(monkeypatch):
    teacher_id = await create_user(
        email=f"dwell-dt-{uuid.uuid4().hex[:8]}@example.com", role="teacher"
    )
    student_id = await create_user(
        email=f"dwell-ds-{uuid.uuid4().hex[:8]}@example.com"
    )
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)

    async with SessionLocal() as db:
        await db.execute(
            delete(BackgroundJob).where(BackgroundJob.lesson_id == ids["lesson_id"])
        )
        session = LearningSession(
            enrollment_id=ids["enrollment_id"],
            lesson_id=ids["lesson_id"],
            status="completed",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(session)
        await db.flush()
        db.add(
            ContentView(
                session_id=session.id,
                surface="quiz",
                sequence_no=0,
                analysis_status="pending",
            )
        )
        job = BackgroundJob(
            lesson_id=ids["lesson_id"],
            kind="analyze_lesson",
            status="processing",
            attempts=3,
            max_attempts=3,
        )
        db.add(job)
        await db.commit()
        job_id = job.id

    async def fake_analyze(lesson_id: str) -> tuple[int, int]:
        return (0, 0)

    monkeypatch.setattr(analysis, "analyze_lesson", fake_analyze)

    async with SessionLocal() as db:
        claimed = await db.get(BackgroundJob, job_id)
    assert claimed is not None
    await analysis._process_job(claimed)

    async with SessionLocal() as db:
        stored = await db.get(BackgroundJob, job_id)
        queued_count = len(
            (
                await db.execute(
                    select(BackgroundJob.id).where(
                        BackgroundJob.lesson_id == ids["lesson_id"],
                        BackgroundJob.status == "queued",
                    )
                )
            ).scalars().all()
        )
        await db.execute(
            delete(BackgroundJob).where(BackgroundJob.lesson_id == ids["lesson_id"])
        )
        await db.commit()

    # Không còn lượt thử: job kết thúc failed thay vì xếp vòng lặp vô hạn.
    assert stored is not None and stored.status == "failed"
    assert queued_count == 0
