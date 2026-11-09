import hashlib
import uuid
from datetime import datetime, timezone

import pytest

from app.db.session import engine
from tests.conftest import create_user, login, seed_course
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
async def test_gaze_batch_idempotency_and_order(client):
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

    out_of_order = await client.post(
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
    assert out_of_order.status_code == 409


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
    # session+enrollment, presentation, batch+max, insert batch, insert samples.
    assert counter.count <= 5, "\n\n".join(counter.statements)
