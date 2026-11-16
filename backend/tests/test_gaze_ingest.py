import hashlib
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.db.session import SessionLocal, engine
from app.models.gaze import ContentView, GazeSample
from tests.conftest import create_user, login, seed_course, seed_slide
from tests.query_counter import count_queries


def _payload_hash() -> str:
    return hashlib.sha256(b"test-payload").hexdigest()


def _sample(sequence: int) -> dict:
    return {
        "sequence": sequence,
        "captureMonotonicNs": sequence * 1_000_000,
        "eventTime": datetime.now(timezone.utc).isoformat(),
        "viewportX": 0.5,
        "viewportY": 0.5,
        "status": "ok",
        "qualityFlags": {},
    }


@pytest.mark.asyncio
async def test_gaze_batch_idempotency_without_batch_table(client):
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)

    token = await login(client, student_email)
    headers = {"Authorization": f"Bearer {token}"}

    session_response = await client.post(
        "/api/learning-sessions",
        headers=headers,
        json={
            "enrollmentId": ids["enrollment_id"],
            "lessonId": ids["lesson_id"],
            "deviceFingerprint": "test-device",
            "viewportWidthPx": 1280,
            "viewportHeightPx": 720,
            "calibrationWidthPx": 1280,
            "calibrationHeightPx": 720,
            "devicePixelRatio": 1.0,
            "trackingConsent": True,
        },
    )
    assert session_response.status_code == 201, session_response.text
    session_id = session_response.json()["id"]

    presentation_response = await client.post(
        f"/api/learning-sessions/{session_id}/presentations",
        headers=headers,
        json={"surface": "quiz", "sequenceNo": 0},
    )
    assert presentation_response.status_code == 201, presentation_response.text
    presentation_id = presentation_response.json()["id"]

    batch_id = str(uuid.uuid4())
    batch = {
        "batchId": batch_id,
        "batchNo": 0,
        "presentationId": presentation_id,
        "sequenceStart": 0,
        "sequenceEnd": 1,
        "payloadHash": _payload_hash(),
        "samples": [_sample(0), _sample(1)],
    }

    first = await client.post(
        f"/api/learning-sessions/{session_id}/gaze-batches",
        headers=headers,
        json=batch,
    )
    assert first.status_code == 200, first.text
    assert first.json()["stored"] == 2

    duplicate = await client.post(
        f"/api/learning-sessions/{session_id}/gaze-batches",
        headers=headers,
        json=batch,
    )
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["duplicate"] == 2
    assert duplicate.json()["stored"] == 0

    # Không còn batch number/order toàn cục: batch mới chỉ cần idempotent theo
    # (content_view_id, client_batch_id, sequence).
    later_batch = await client.post(
        f"/api/learning-sessions/{session_id}/gaze-batches",
        headers=headers,
        json={
            "batchId": str(uuid.uuid4()),
            "batchNo": 5,
            "presentationId": presentation_id,
            "sequenceStart": 2,
            "sequenceEnd": 2,
            "payloadHash": _payload_hash(),
            "samples": [_sample(2)],
        },
    )
    assert later_batch.status_code == 200
    assert later_batch.json()["stored"] == 1


@pytest.mark.asyncio
async def test_gaze_batch_query_count(client):
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)

    token = await login(client, student_email)
    headers = {"Authorization": f"Bearer {token}"}

    session_response = await client.post(
        "/api/learning-sessions",
        headers=headers,
        json={
            "enrollmentId": ids["enrollment_id"],
            "lessonId": ids["lesson_id"],
            "deviceFingerprint": "test-device",
            "viewportWidthPx": 1280,
            "viewportHeightPx": 720,
            "calibrationWidthPx": 1280,
            "calibrationHeightPx": 720,
            "devicePixelRatio": 1.0,
            "trackingConsent": True,
        },
    )
    assert session_response.status_code == 201, session_response.text
    session_id = session_response.json()["id"]

    presentation_response = await client.post(
        f"/api/learning-sessions/{session_id}/presentations",
        headers=headers,
        json={"surface": "quiz", "sequenceNo": 0},
    )
    assert presentation_response.status_code == 201, presentation_response.text
    presentation_id = presentation_response.json()["id"]

    batch = {
        "batchId": str(uuid.uuid4()),
        "batchNo": 0,
        "presentationId": presentation_id,
        "sequenceStart": 0,
        "sequenceEnd": 1,
        "payloadHash": _payload_hash(),
        "samples": [_sample(0), _sample(1)],
    }

    # Warm auth cache (Redis hoặc fallback in-process) để đo đúng hot path.
    warm = await client.get("/api/me/enrollments", headers=headers)
    assert warm.status_code == 200, warm.text

    with count_queries(engine) as counter:
        response = await client.post(
            f"/api/learning-sessions/{session_id}/gaze-batches",
            headers=headers,
            json=batch,
        )

    assert response.status_code == 200, response.text
    assert response.json()["stored"] == 2
    # session+enrollment, presentation, insert samples, update analysis status.
    assert counter.count <= 5, "\n\n".join(counter.statements)


@pytest.mark.asyncio
async def test_gaze_batches_bound_to_their_presentation(client):
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    slide = await seed_slide(
        course_id=ids["course_id"],
        lesson_id=ids["lesson_id"],
        teacher_id=teacher_id,
    )

    token = await login(client, student_email)
    headers = {"Authorization": f"Bearer {token}"}

    session_response = await client.post(
        "/api/learning-sessions",
        headers=headers,
        json={
            "enrollmentId": ids["enrollment_id"],
            "lessonId": ids["lesson_id"],
            "deviceFingerprint": "test-device",
            "viewportWidthPx": 1280,
            "viewportHeightPx": 720,
            "calibrationWidthPx": 1280,
            "calibrationHeightPx": 720,
            "devicePixelRatio": 1.0,
            "trackingConsent": True,
        },
    )
    assert session_response.status_code == 201, session_response.text
    session_id = session_response.json()["id"]

    view_ids = []
    for _ in range(2):
        created = await client.post(
            f"/api/learning-sessions/{session_id}/presentations",
            headers=headers,
            json={
                "clientPresentationId": str(uuid.uuid4()),
                "slideId": slide["slide_id"],
                "surface": "lesson",
            },
        )
        assert created.status_code == 201, created.text
        view_ids.append(created.json()["id"])
    assert view_ids[0] != view_ids[1]

    for view_id in view_ids:
        response = await client.post(
            f"/api/learning-sessions/{session_id}/gaze-batches",
            headers=headers,
            json={
                "batchId": str(uuid.uuid4()),
                "batchNo": 0,
                "presentationId": view_id,
                "sequenceStart": 0,
                "sequenceEnd": 1,
                "payloadHash": _payload_hash(),
                "samples": [_sample(0), _sample(1)],
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["stored"] == 2

    async with SessionLocal() as db:
        counts = dict(
            (
                await db.execute(
                    select(GazeSample.content_view_id, func.count())
                    .where(GazeSample.content_view_id.in_(view_ids))
                    .group_by(GazeSample.content_view_id)
                )
            ).all()
        )
        assert counts == {view_ids[0]: 2, view_ids[1]: 2}

        views = list(
            (
                await db.execute(
                    select(ContentView)
                    .where(ContentView.id.in_(view_ids))
                    .order_by(ContentView.sequence_no)
                )
            ).scalars()
        )
        assert [view.sequence_no for view in views] == [0, 1]
        assert views[0].ended_at is not None
        assert views[0].analysis_status == "pending"
        assert views[1].ended_at is None
