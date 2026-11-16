"""Vòng đời content_views với clientPresentationId (không lọc lượt xem)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.gaze import ContentView
from tests.conftest import create_user, login, seed_course, seed_slide


def _session_payload(
    enrollment_id: str,
    lesson_id: str,
    *,
    visit_id: str | None = None,
    viewport_width: int = 1280,
) -> dict:
    return {
        "enrollmentId": enrollment_id,
        "lessonId": lesson_id,
        "courseVisitId": visit_id,
        "deviceFingerprint": "lifecycle-device",
        "viewportWidthPx": viewport_width,
        "viewportHeightPx": 720,
        "calibrationWidthPx": 1280,
        "calibrationHeightPx": 720,
        "devicePixelRatio": 1.0,
        "trackingConsent": True,
    }


async def _start_session(client, headers: dict, payload: dict) -> str:
    response = await client.post(
        "/api/learning-sessions", headers=headers, json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _enter(
    client,
    headers: dict,
    session_id: str,
    *,
    client_id: str | None = None,
    slide_id: str | None = None,
    surface: str = "lesson",
    sequence_no: int | None = None,
    entered_at: datetime | None = None,
):
    payload: dict = {"surface": surface}
    if client_id is not None:
        payload["clientPresentationId"] = client_id
    if slide_id is not None:
        payload["slideId"] = slide_id
    if sequence_no is not None:
        payload["sequenceNo"] = sequence_no
    if entered_at is not None:
        payload["enteredAt"] = entered_at.isoformat()
    return await client.post(
        f"/api/learning-sessions/{session_id}/presentations",
        headers=headers,
        json=payload,
    )


async def _views(session_id: str) -> list[ContentView]:
    async with SessionLocal() as db:
        return list(
            (
                await db.execute(
                    select(ContentView)
                    .where(ContentView.session_id == session_id)
                    .order_by(ContentView.sequence_no)
                )
            ).scalars()
        )


async def _setup(client, *, slide_count: int = 1):
    teacher_email = f"lc-t-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"lc-s-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    slides = [
        (
            await seed_slide(
                course_id=ids["course_id"],
                lesson_id=ids["lesson_id"],
                teacher_id=teacher_id,
                position=position,
            )
        )["slide_id"]
        for position in range(slide_count)
    ]
    token = await login(client, student_email)
    headers = {"Authorization": f"Bearer {token}"}
    session_id = await _start_session(
        client, headers, _session_payload(ids["enrollment_id"], ids["lesson_id"])
    )
    return {
        "ids": ids,
        "slides": slides,
        "teacher_id": teacher_id,
        "student_id": student_id,
        "headers": headers,
        "session_id": session_id,
    }


@pytest.mark.asyncio
async def test_new_client_id_same_slide_creates_new_view(client):
    ctx = await _setup(client)
    headers = ctx["headers"]
    session_id = ctx["session_id"]
    slide_id = ctx["slides"][0]

    first_entered = datetime.now(timezone.utc) - timedelta(seconds=5)
    first = await _enter(
        client,
        headers,
        session_id,
        client_id=str(uuid.uuid4()),
        slide_id=slide_id,
        entered_at=first_entered,
    )
    assert first.status_code == 201, first.text
    first_body = first.json()
    assert first_body["sequenceNo"] == 0

    second_entered = datetime.now(timezone.utc)
    second = await _enter(
        client,
        headers,
        session_id,
        client_id=str(uuid.uuid4()),
        slide_id=slide_id,
        entered_at=second_entered,
    )
    assert second.status_code == 201, second.text
    second_body = second.json()
    assert second_body["id"] != first_body["id"]
    assert second_body["sequenceNo"] == 1

    rows = await _views(session_id)
    assert [row.sequence_no for row in rows] == [0, 1]
    assert rows[0].slide_id == slide_id
    assert rows[0].started_at == first_entered
    # Lượt cũ được đóng tại enteredAt của lượt mới, không bị ghi đè.
    assert rows[0].ended_at is not None
    assert rows[0].ended_at == datetime.fromisoformat(second_body["startedAt"])
    assert rows[1].ended_at is None


@pytest.mark.asyncio
async def test_same_client_id_is_idempotent(client):
    ctx = await _setup(client)
    headers = ctx["headers"]
    session_id = ctx["session_id"]
    client_id = str(uuid.uuid4())

    first = await _enter(
        client,
        headers,
        session_id,
        client_id=client_id,
        slide_id=ctx["slides"][0],
    )
    assert first.status_code == 201, first.text

    retry = await _enter(
        client,
        headers,
        session_id,
        client_id=client_id,
        slide_id=ctx["slides"][0],
        entered_at=datetime.now(timezone.utc) + timedelta(seconds=1),
    )
    assert retry.status_code == 201, retry.text
    assert retry.json()["id"] == first.json()["id"]
    assert retry.json()["sequenceNo"] == first.json()["sequenceNo"]

    rows = await _views(session_id)
    assert len(rows) == 1
    assert rows[0].ended_at is None


@pytest.mark.asyncio
async def test_client_id_conflict_on_different_context(client):
    ctx = await _setup(client, slide_count=2)
    headers = ctx["headers"]
    session_id = ctx["session_id"]
    client_id = str(uuid.uuid4())

    first = await _enter(
        client,
        headers,
        session_id,
        client_id=client_id,
        slide_id=ctx["slides"][0],
    )
    assert first.status_code == 201, first.text

    # Cùng session nhưng khác slide.
    other_slide = await _enter(
        client,
        headers,
        session_id,
        client_id=client_id,
        slide_id=ctx["slides"][1],
    )
    assert other_slide.status_code == 409, other_slide.text
    assert other_slide.json()["detail"]["code"] == "presentation_conflict"

    # Cùng UUID ở session khác.
    other_ids = await seed_course(
        teacher_id=ctx["teacher_id"], student_id=ctx["student_id"], title="Course 2"
    )
    other_slide_id = (
        await seed_slide(
            course_id=other_ids["course_id"],
            lesson_id=other_ids["lesson_id"],
            teacher_id=ctx["teacher_id"],
        )
    )["slide_id"]
    other_session_id = await _start_session(
        client,
        headers,
        _session_payload(other_ids["enrollment_id"], other_ids["lesson_id"]),
    )
    other_session = await _enter(
        client,
        headers,
        other_session_id,
        client_id=client_id,
        slide_id=other_slide_id,
    )
    assert other_session.status_code == 409, other_session.text
    assert other_session.json()["detail"]["code"] == "presentation_conflict"


@pytest.mark.asyncio
async def test_stale_entered_at_rejected(client):
    ctx = await _setup(client)
    headers = ctx["headers"]
    session_id = ctx["session_id"]

    first_entered = datetime.now(timezone.utc) - timedelta(seconds=2)
    first = await _enter(
        client,
        headers,
        session_id,
        client_id=str(uuid.uuid4()),
        slide_id=ctx["slides"][0],
        entered_at=first_entered,
    )
    assert first.status_code == 201, first.text

    stale = await _enter(
        client,
        headers,
        session_id,
        client_id=str(uuid.uuid4()),
        slide_id=ctx["slides"][0],
        entered_at=first_entered - timedelta(seconds=1),
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"]["code"] == "stale_presentation"

    rows = await _views(session_id)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_entered_at_is_clamped_to_server_window(client):
    ctx = await _setup(client)
    headers = ctx["headers"]
    session_id = ctx["session_id"]

    before = datetime.now(timezone.utc)
    too_old = await _enter(
        client,
        headers,
        session_id,
        client_id=str(uuid.uuid4()),
        slide_id=ctx["slides"][0],
        entered_at=before - timedelta(hours=1),
    )
    after = datetime.now(timezone.utc)
    assert too_old.status_code == 201, too_old.text
    started = datetime.fromisoformat(too_old.json()["startedAt"])
    assert before - timedelta(minutes=5) <= started
    assert started <= after - timedelta(minutes=5) + timedelta(seconds=1)

    future = await _enter(
        client,
        headers,
        session_id,
        client_id=str(uuid.uuid4()),
        slide_id=ctx["slides"][0],
        entered_at=after + timedelta(minutes=10),
    )
    assert future.status_code == 201, future.text
    started_future = datetime.fromisoformat(future.json()["startedAt"])
    assert started_future <= datetime.now(timezone.utc) + timedelta(seconds=1)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["completed", "aborted"])
async def test_end_session_closes_open_views(client, status: str):
    ctx = await _setup(client)
    headers = ctx["headers"]
    session_id = ctx["session_id"]

    entered = await _enter(
        client,
        headers,
        session_id,
        client_id=str(uuid.uuid4()),
        slide_id=ctx["slides"][0],
    )
    assert entered.status_code == 201, entered.text

    ended = await client.patch(
        f"/api/learning-sessions/{session_id}",
        headers=headers,
        json={"status": status},
    )
    assert ended.status_code == 200, ended.text

    rows = await _views(session_id)
    assert len(rows) == 1
    assert rows[0].ended_at is not None
    assert rows[0].ended_at >= rows[0].started_at


@pytest.mark.asyncio
async def test_new_session_aborts_old_and_closes_views(client):
    ctx = await _setup(client)
    headers = ctx["headers"]
    session_id = ctx["session_id"]

    entered = await _enter(
        client,
        headers,
        session_id,
        client_id=str(uuid.uuid4()),
        slide_id=ctx["slides"][0],
    )
    assert entered.status_code == 201, entered.text

    # Viewport khác → không tái dùng session cũ mà abort rồi tạo session mới.
    new_session_id = await _start_session(
        client,
        headers,
        _session_payload(
            ctx["ids"]["enrollment_id"], ctx["ids"]["lesson_id"], viewport_width=1920
        ),
    )
    assert new_session_id != session_id

    rows = await _views(session_id)
    assert len(rows) == 1
    assert rows[0].ended_at is not None


@pytest.mark.asyncio
async def test_end_course_visit_closes_open_views(client):
    ctx = await _setup(client)
    headers = ctx["headers"]

    visit = await client.post(
        "/api/course-visits",
        headers=headers,
        json={"enrollmentId": ctx["ids"]["enrollment_id"], "visitKey": "lc-tab"},
    )
    assert visit.status_code == 201, visit.text
    visit_id = visit.json()["id"]

    session_id = await _start_session(
        client,
        headers,
        _session_payload(
            ctx["ids"]["enrollment_id"], ctx["ids"]["lesson_id"], visit_id=visit_id
        ),
    )
    entered = await _enter(
        client,
        headers,
        session_id,
        client_id=str(uuid.uuid4()),
        slide_id=ctx["slides"][0],
    )
    assert entered.status_code == 201, entered.text

    ended = await client.patch(
        f"/api/course-visits/{visit_id}", headers=headers, json={"status": "ended"}
    )
    assert ended.status_code == 200, ended.text

    rows = await _views(session_id)
    assert len(rows) == 1
    assert rows[0].ended_at is not None


@pytest.mark.asyncio
async def test_legacy_sequence_no_still_idempotent(client):
    ctx = await _setup(client)
    headers = ctx["headers"]
    session_id = ctx["session_id"]

    first = await _enter(
        client,
        headers,
        session_id,
        slide_id=ctx["slides"][0],
        sequence_no=0,
    )
    assert first.status_code == 201, first.text
    assert first.json()["sequenceNo"] == 0

    retry = await _enter(
        client,
        headers,
        session_id,
        slide_id=ctx["slides"][0],
        sequence_no=0,
    )
    assert retry.status_code == 201, retry.text
    assert retry.json()["id"] == first.json()["id"]

    # sequenceNo trùng nhưng khác surface → row mới, sequence kế tiếp.
    collision = await _enter(
        client, headers, session_id, surface="quiz", sequence_no=0
    )
    assert collision.status_code == 201, collision.text
    assert collision.json()["id"] != first.json()["id"]
    assert collision.json()["sequenceNo"] == 1

    # Client mới có thể bỏ hẳn sequenceNo.
    auto = await _enter(client, headers, session_id, surface="quiz")
    assert auto.status_code == 201, auto.text
    assert auto.json()["sequenceNo"] == 2

    rows = await _views(session_id)
    assert [row.sequence_no for row in rows] == [0, 1, 2]
