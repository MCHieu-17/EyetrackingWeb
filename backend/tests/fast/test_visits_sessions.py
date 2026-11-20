"""Khóa vòng đời ca học và phiên học."""

from __future__ import annotations

import pytest

from tests.conftest import (
    create_calibration,
    create_course,
    create_lesson,
    create_user,
    execute,
    fetch_one,
    login,
)

pytestmark = pytest.mark.fast

SESSION_BODY = {
    "deviceFingerprint": "test-device",
    "viewportWidthPx": 1280,
    "viewportHeightPx": 720,
    "calibrationWidthPx": 1280,
    "calibrationHeightPx": 720,
    "devicePixelRatio": 1.0,
    "trackingConsent": True,
}


async def _student_course(
    client,
    *,
    email="student-visit@example.com",
    published=True,
    require_calibration=False,
):
    teacher = await create_user(role="teacher", email=f"t-{email}")
    student = await create_user(email=email)
    ids = await create_course(
        teacher_id=teacher["id"],
        student_id=student["id"],
        status="published" if published else "draft",
        require_calibration=require_calibration,
    )
    lesson_id = await create_lesson(module_id=ids["module_id"])
    await login(client, student["email"])
    return student, ids, lesson_id


async def test_visit_create_is_idempotent_and_active(client):
    _, ids, _ = await _student_course(client)
    first = await client.post(
        "/api/course-visits",
        json={"enrollmentId": ids["enrollment_id"], "visitKey": "tab-1"},
    )
    assert first.status_code == 201, first.text
    visit_id = first.json()["id"]
    assert first.json()["status"] == "active"

    second = await client.post(
        "/api/course-visits",
        json={"enrollmentId": ids["enrollment_id"], "visitKey": "tab-1"},
    )
    assert second.status_code == 201
    assert second.json()["id"] == visit_id

    active = await client.get(
        "/api/course-visits/active",
        params={"enrollmentId": ids["enrollment_id"]},
    )
    assert active.status_code == 200
    assert active.json()["id"] == visit_id

    heartbeat = await client.post(f"/api/course-visits/{visit_id}/heartbeat")
    assert heartbeat.status_code == 200
    assert heartbeat.json()["id"] == visit_id

    ended = await client.patch(
        f"/api/course-visits/{visit_id}", json={"status": "ended"}
    )
    assert ended.status_code == 200
    assert ended.json()["status"] == "ended"
    assert ended.json()["endedAt"]

    closed = await client.post(f"/api/course-visits/{visit_id}/heartbeat")
    assert closed.status_code == 409
    assert closed.json()["detail"]["code"] == "visit_closed"


async def test_visit_of_other_student_is_forbidden(client_factory):
    first = await client_factory()
    _, ids, _ = await _student_course(first, email="visit-owner@example.com")
    visit = await first.post(
        "/api/course-visits", json={"enrollmentId": ids["enrollment_id"]}
    )
    second = await client_factory()
    other = await create_user(email="visit-other@example.com")
    await login(second, other["email"])
    assert (
        await second.post(
            "/api/course-visits",
            json={"enrollmentId": ids["enrollment_id"]},
        )
    ).status_code == 403
    assert (
        await second.patch(
            f"/api/course-visits/{visit.json()['id']}", json={"status": "ended"}
        )
    ).status_code == 403


async def test_session_create_continue_and_abort(client):
    student, ids, lesson_id = await _student_course(
        client, email="session-flow@example.com"
    )
    visit = await client.post(
        "/api/course-visits", json={"enrollmentId": ids["enrollment_id"]}
    )
    visit_id = visit.json()["id"]
    first = await client.post(
        "/api/learning-sessions",
        json={
            **SESSION_BODY,
            "enrollmentId": ids["enrollment_id"],
            "lessonId": lesson_id,
            "courseVisitId": visit_id,
        },
    )
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["mode"] == "first"
    assert body["status"] == "in_progress"
    assert body["calibrated"] is False
    assert body["courseVisitId"] == visit_id

    continued = await client.post(
        "/api/learning-sessions",
        json={
            **SESSION_BODY,
            "enrollmentId": ids["enrollment_id"],
            "lessonId": lesson_id,
            "courseVisitId": visit_id,
        },
    )
    assert continued.status_code == 201
    assert continued.json()["id"] == body["id"]
    assert continued.json()["mode"] == "continue"

    newer = await create_calibration(user_id=student["id"])
    replaced = await client.post(
        "/api/learning-sessions",
        json={
            **SESSION_BODY,
            "enrollmentId": ids["enrollment_id"],
            "lessonId": lesson_id,
            "courseVisitId": visit_id,
        },
    )
    assert replaced.status_code == 201
    assert replaced.json()["id"] != body["id"]
    assert replaced.json()["calibrationId"] == newer
    assert (
        await fetch_one(
            "SELECT status FROM learning_sessions WHERE id = :id", {"id": body["id"]}
        )
    )["status"] == "aborted"


async def test_session_requires_calibration(client):
    _, ids, lesson_id = await _student_course(
        client, email="session-cal@example.com", require_calibration=True
    )
    response = await client.post(
        "/api/learning-sessions",
        json={
            **SESSION_BODY,
            "enrollmentId": ids["enrollment_id"],
            "lessonId": lesson_id,
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "calibration_required"


async def test_session_rejects_archived_dropped_and_foreign(client_factory):
    first = await client_factory()
    _, ids, lesson_id = await _student_course(first, email="session-errors@example.com")
    archived_teacher = await create_user(role="teacher", email="arch@example.com")
    archived = await create_course(
        teacher_id=archived_teacher["id"],
        student_id=(await create_user(email="arch-student@example.com"))["id"],
        status="archived",
    )
    archived_lesson = await create_lesson(module_id=archived["module_id"])
    await execute(
        "UPDATE courses SET status = 'archived' WHERE id = :id",
        {"id": archived["course_id"]},
    )
    archived_client = await client_factory()
    await login(archived_client, "arch-student@example.com")
    response = await archived_client.post(
        "/api/learning-sessions",
        json={
            **SESSION_BODY,
            "enrollmentId": archived["enrollment_id"],
            "lessonId": archived_lesson,
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "course_archived"

    await execute(
        "UPDATE enrollments SET status = 'dropped' WHERE id = :id",
        {"id": ids["enrollment_id"]},
    )
    dropped = await first.post(
        "/api/learning-sessions",
        json={
            **SESSION_BODY,
            "enrollmentId": ids["enrollment_id"],
            "lessonId": lesson_id,
        },
    )
    assert dropped.status_code == 403

    other = await client_factory()
    other_user = await create_user(email="session-other@example.com")
    await login(other, other_user["email"])
    foreign = await other.post(
        "/api/learning-sessions",
        json={
            **SESSION_BODY,
            "enrollmentId": ids["enrollment_id"],
            "lessonId": lesson_id,
        },
    )
    assert foreign.status_code == 403


async def test_session_closed_visit_conflict(client):
    _, ids, lesson_id = await _student_course(client, email="session-visit@example.com")
    visit = await client.post(
        "/api/course-visits", json={"enrollmentId": ids["enrollment_id"]}
    )
    visit_id = visit.json()["id"]
    await client.patch(f"/api/course-visits/{visit_id}", json={"status": "ended"})
    response = await client.post(
        "/api/learning-sessions",
        json={
            **SESSION_BODY,
            "enrollmentId": ids["enrollment_id"],
            "lessonId": lesson_id,
            "courseVisitId": visit_id,
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "visit_closed"

    other_teacher = await create_user(role="teacher", email="visit-conflict@example.com")
    other_course = await create_course(teacher_id=other_teacher["id"])
    # Dùng visit của enrollment khác (tạo enrollment thứ hai cho cùng student).
    await execute(
        "INSERT INTO enrollments (id, course_id, student_id, status) "
        "VALUES (:id, :course, :student, 'active')",
        {
            "id": "00000000-0000-4000-8000-000000000001",
            "course": other_course["course_id"],
            "student": (await fetch_one(
                "SELECT student_id FROM enrollments WHERE id = :id",
                {"id": ids["enrollment_id"]},
            ))["student_id"],
        },
    )
    await execute(
        "INSERT INTO course_visits (id, enrollment_id, visit_key) "
        "VALUES ('00000000-0000-4000-8000-000000000002', "
        "'00000000-0000-4000-8000-000000000001', 'foreign')"
    )
    conflict = await client.post(
        "/api/learning-sessions",
        json={
            **SESSION_BODY,
            "enrollmentId": ids["enrollment_id"],
            "lessonId": lesson_id,
            "courseVisitId": "00000000-0000-4000-8000-000000000002",
        },
    )
    assert conflict.status_code == 400
    assert conflict.json()["detail"]["code"] == "visit_conflict"


async def test_session_contents_and_end_session(client, client_factory):
    _student, ids, lesson_id = await _student_course(
        client, email="session-end@example.com"
    )
    created = await client.post(
        "/api/learning-sessions",
        json={
            **SESSION_BODY,
            "enrollmentId": ids["enrollment_id"],
            "lessonId": lesson_id,
        },
    )
    assert created.status_code == 201
    session_id = created.json()["id"]

    contents = await client.get(f"/api/learning-sessions/{session_id}/contents")
    assert contents.status_code == 200
    assert isinstance(contents.json(), list)

    other = await client_factory()
    other_user = await create_user(email="session-contents-other@example.com")
    await login(other, other_user["email"])
    assert (
        await other.get(f"/api/learning-sessions/{session_id}/contents")
    ).status_code == 403

    ended = await client.patch(
        f"/api/learning-sessions/{session_id}", json={"status": "completed"}
    )
    assert ended.status_code == 200
    assert ended.json()["status"] == "completed"
    job = await fetch_one(
        "SELECT kind, status FROM background_jobs "
        "WHERE lesson_id = :lesson ORDER BY created_at DESC LIMIT 1",
        {"lesson": lesson_id},
    )
    assert job["kind"] == "analyze_lesson"
    assert job["status"] == "queued"

    again = await client.patch(
        f"/api/learning-sessions/{session_id}", json={"status": "completed"}
    )
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "session_closed"
