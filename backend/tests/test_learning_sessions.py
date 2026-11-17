import asyncio
import uuid

import pytest
from sqlalchemy import func, select

from app.models.course import Course
from app.models.gaze import LearningSession
from tests.conftest import SessionLocal, create_user, login, seed_course


async def _create_session(client, headers: dict, ids: dict) -> str:
    response = await client.post(
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
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.mark.asyncio
async def test_concurrent_session_creation_reuses_one_active_session(client):
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    token = await login(client, student_email)
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "enrollmentId": ids["enrollment_id"],
        "lessonId": ids["lesson_id"],
        "deviceFingerprint": "race-device",
        "viewportWidthPx": 1280,
        "viewportHeightPx": 720,
        "calibrationWidthPx": 1280,
        "calibrationHeightPx": 720,
        "devicePixelRatio": 1.0,
        "trackingConsent": True,
    }

    first, second = await asyncio.gather(
        client.post("/api/learning-sessions", headers=headers, json=payload),
        client.post("/api/learning-sessions", headers=headers, json=payload),
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]
    async with SessionLocal() as db:
        active = (
            await db.execute(
                select(func.count(LearningSession.id)).where(
                    LearningSession.enrollment_id == ids["enrollment_id"],
                    LearningSession.lesson_id == ids["lesson_id"],
                    LearningSession.status == "in_progress",
                )
            )
        ).scalar_one()
    assert active == 1


@pytest.mark.asyncio
async def test_end_session_and_get_contents(client):
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)

    token = await login(client, student_email)
    headers = {"Authorization": f"Bearer {token}"}
    session_id = await _create_session(client, headers, ids)

    contents = await client.get(
        f"/api/learning-sessions/{session_id}/contents", headers=headers
    )
    assert contents.status_code == 200, contents.text
    assert contents.json() == []

    ended = await client.patch(
        f"/api/learning-sessions/{session_id}",
        headers=headers,
        json={"status": "completed"},
    )
    assert ended.status_code == 200, ended.text
    assert ended.json()["status"] == "completed"

    again = await client.patch(
        f"/api/learning-sessions/{session_id}",
        headers=headers,
        json={"status": "completed"},
    )
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "session_closed"


@pytest.mark.asyncio
async def test_archived_course_cannot_start_new_learning_session(client):
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)

    async with SessionLocal() as db:
        course = await db.get(Course, ids["course_id"])
        assert course is not None
        course.status = "archived"
        await db.commit()

    token = await login(client, student_email)
    response = await client.post(
        "/api/learning-sessions",
        headers={"Authorization": f"Bearer {token}"},
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
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "course_archived"


@pytest.mark.asyncio
async def test_session_access_control(client):
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    other_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    await create_user(email=other_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)

    token = await login(client, student_email)
    headers = {"Authorization": f"Bearer {token}"}
    other_token = await login(client, other_email)
    other_headers = {"Authorization": f"Bearer {other_token}"}
    session_id = await _create_session(client, headers, ids)

    contents = await client.get(
        f"/api/learning-sessions/{session_id}/contents", headers=other_headers
    )
    assert contents.status_code == 403

    ended = await client.patch(
        f"/api/learning-sessions/{session_id}",
        headers=other_headers,
        json={"status": "completed"},
    )
    assert ended.status_code == 403

    missing_id = str(uuid.uuid4())
    missing_contents = await client.get(
        f"/api/learning-sessions/{missing_id}/contents", headers=headers
    )
    assert missing_contents.status_code == 404

    missing_end = await client.patch(
        f"/api/learning-sessions/{missing_id}",
        headers=headers,
        json={"status": "completed"},
    )
    assert missing_end.status_code == 404
