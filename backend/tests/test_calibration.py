import base64
import uuid

import pytest

from app.models.course import Course
from tests.conftest import SessionLocal, create_user, login, seed_course


@pytest.mark.asyncio
async def test_calibration_screen_origin_and_viewport_change(client):
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(
        teacher_id=teacher_id,
        student_id=student_id,
        require_calibration=True,
    )

    token = await login(client, student_email)
    headers = {"Authorization": f"Bearer {token}"}

    model = base64.b64encode(b"fake-ubj-model").decode("ascii")
    calibration_response = await client.post(
        "/api/calibrations",
        headers=headers,
        json={
            "deviceFingerprint": "test-device",
            "numPoints": 25,
            "modelUbjBase64": model,
            "screenWidthPx": 1600,
            "screenHeightPx": 900,
            "viewportWidthPx": 1600,
            "viewportHeightPx": 900,
            "devicePixelRatio": 1.0,
            "screenXPx": 120,
            "screenYPx": 80,
        },
    )
    assert calibration_response.status_code == 201, calibration_response.text
    body = calibration_response.json()
    assert body["screenXPx"] == 120
    assert body["screenYPx"] == 80

    active_response = await client.get(
        "/api/calibrations/active",
        headers=headers,
        params={"deviceFingerprint": "test-device"},
    )
    assert active_response.status_code == 200, active_response.text
    active = active_response.json()
    assert active["screenXPx"] == 120
    assert active["screenYPx"] == 80

    # Viewport khác lúc calibration (zoom/resize) vẫn tạo được phiên.
    session_response = await client.post(
        "/api/learning-sessions",
        headers=headers,
        json={
            "enrollmentId": ids["enrollment_id"],
            "lessonId": ids["lesson_id"],
            "deviceFingerprint": "test-device",
            "viewportWidthPx": 1280,
            "viewportHeightPx": 720,
            "calibrationWidthPx": 1600,
            "calibrationHeightPx": 900,
            "devicePixelRatio": 1.25,
            "trackingConsent": True,
        },
    )
    assert session_response.status_code == 201, session_response.text


@pytest.mark.asyncio
async def test_require_calibration_toggle_bumps_updated_at_and_invalidates_cache(
    client, monkeypatch
):
    """Đổi cờ hiệu chỉnh phải làm mới cache outline và cache enrollment."""
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(
        teacher_id=teacher_id,
        student_id=student_id,
        require_calibration=True,
    )

    async with SessionLocal() as db:
        course = await db.get(Course, ids["course_id"])
        assert course is not None
        before = course.updated_at

    deleted: list[str] = []

    async def fake_delete(key: str) -> None:
        deleted.append(key)

    monkeypatch.setattr("app.api.routes.courses.cache_delete", fake_delete)

    token = await login(client, teacher_email)
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.patch(
        f"/teacher/courses/{ids['course_id']}/require-calibration",
        headers=headers,
        json={"requireCalibration": False},
    )
    assert response.status_code == 200, response.text
    assert response.json()["requireCalibration"] is False

    async with SessionLocal() as db:
        course = await db.get(Course, ids["course_id"])
        assert course is not None
        assert course.require_calibration is False
        assert course.updated_at > before

    assert f"student:enrollments:{student_id}" in deleted
