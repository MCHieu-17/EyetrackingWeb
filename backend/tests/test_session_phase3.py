"""Phase 3 smoke: calibration → learning session → session-pinned contents."""

from __future__ import annotations

import asyncio
import base64

import pymupdf
import pytest

from tests.conftest import auth, login, make_user


def _pdf_bytes() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Session slide")
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture()
def teacher(client):
    asyncio.run(make_user("teacher4@example.com", "teacher", full_name="GV Phase 3B"))
    return login(client, "teacher4@example.com")


@pytest.fixture()
def student(client):
    asyncio.run(make_user("student4@example.com", "student", full_name="SV Phase 3B"))
    return login(client, "student4@example.com")


def _published_lesson(client, teacher):
    headers = auth(teacher)
    course = client.post(
        "/teacher/courses", json={"title": "Khóa Session"}, headers=headers
    ).json()
    module = client.post(
        f"/teacher/courses/{course['id']}/modules",
        json={"title": "Chương"},
        headers=headers,
    ).json()
    lesson = client.post(
        f"/teacher/modules/{module['id']}/lessons",
        json={"title": "Bài"},
        headers=headers,
    ).json()
    upload = client.post(
        f"/teacher/lessons/{lesson['id']}/slides/upload",
        files={"pdf": ("session.pdf", _pdf_bytes(), "application/pdf")},
        headers=headers,
    )
    assert upload.status_code == 201, upload.text
    published = client.post(
        f"/teacher/courses/{course['id']}/publish", json={}, headers=headers
    )
    assert published.status_code == 200, published.text
    return course["id"], lesson["id"]


def test_calibration_and_learning_session(client, teacher, student):
    course_id, lesson_id = _published_lesson(client, teacher)
    student_headers = auth(student)
    enroll = client.post(f"/api/courses/{course_id}/enroll", headers=student_headers)
    assert enroll.status_code == 201, enroll.text
    enrollment_id = enroll.json()["enrollmentId"]

    fingerprint = "device-phase3"
    calibration = client.post(
        "/api/calibrations",
        json={
            "deviceFingerprint": fingerprint,
            "numPoints": 16,
            "modelUbjBase64": base64.b64encode(b"fake-model").decode(),
            "viewportWidthPx": 1280,
            "viewportHeightPx": 720,
            "devicePixelRatio": 1,
            "maePx": 0.05,
        },
        headers=student_headers,
    )
    assert calibration.status_code == 201, calibration.text

    active = client.get(
        "/api/calibrations/active",
        params={"deviceFingerprint": fingerprint},
        headers=student_headers,
    )
    assert active.status_code == 200, active.text
    assert active.json()["calibrated"] is True

    session = client.post(
        "/api/learning-sessions",
        json={
            "enrollmentId": enrollment_id,
            "lessonId": lesson_id,
            "deviceFingerprint": fingerprint,
            "viewportWidthPx": 1280,
            "viewportHeightPx": 720,
            "calibrationWidthPx": 1280,
            "calibrationHeightPx": 720,
            "devicePixelRatio": 1,
            "trackingConsent": True,
        },
        headers=student_headers,
    )
    assert session.status_code == 201, session.text
    session_id = session.json()["id"]
    assert session.json()["calibrated"] is True

    resumed = client.post(
        "/api/learning-sessions",
        json={
            "enrollmentId": enrollment_id,
            "lessonId": lesson_id,
            "deviceFingerprint": fingerprint,
            "viewportWidthPx": 1280,
            "viewportHeightPx": 720,
            "calibrationWidthPx": 1280,
            "calibrationHeightPx": 720,
            "devicePixelRatio": 1,
            "trackingConsent": True,
        },
        headers=student_headers,
    )
    assert resumed.status_code == 201, resumed.text
    assert resumed.json()["id"] == session_id
    assert resumed.json()["mode"] == "continue"

    contents = client.get(
        f"/api/learning-sessions/{session_id}/contents", headers=student_headers
    )
    assert contents.status_code == 200, contents.text
    assert len(contents.json()) == 1

    closed = client.patch(
        f"/api/learning-sessions/{session_id}",
        json={"status": "completed"},
        headers=student_headers,
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "completed"

    again = client.patch(
        f"/api/learning-sessions/{session_id}",
        json={"status": "completed"},
        headers=student_headers,
    )
    assert again.status_code == 409

    mismatch = client.post(
        "/api/learning-sessions",
        json={
            "enrollmentId": enrollment_id,
            "lessonId": lesson_id,
            "deviceFingerprint": fingerprint,
            "viewportWidthPx": 1024,
            "viewportHeightPx": 768,
            "calibrationWidthPx": 1024,
            "calibrationHeightPx": 768,
            "devicePixelRatio": 1,
            "trackingConsent": True,
        },
        headers=student_headers,
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["detail"]["code"] == "viewport_mismatch"
