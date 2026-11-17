import asyncio
import uuid

import pytest
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.gaze import CourseVisit, LearningSession
from tests.conftest import create_user, login, seed_course


def _session_payload(enrollment_id: str, lesson_id: str, visit_id: str | None):
    return {
        "enrollmentId": enrollment_id,
        "lessonId": lesson_id,
        "courseVisitId": visit_id,
        "deviceFingerprint": "visit-test-device",
        "viewportWidthPx": 1280,
        "viewportHeightPx": 720,
        "calibrationWidthPx": 1280,
        "calibrationHeightPx": 720,
        "devicePixelRatio": 1.0,
        "trackingConsent": True,
    }


@pytest.mark.asyncio
async def test_course_visit_creation_is_idempotent_under_concurrency(client):
    teacher_email = f"visit-t-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"visit-s-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    token = await login(client, student_email)
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"enrollmentId": ids["enrollment_id"], "visitKey": "race-tab"}

    first, second = await asyncio.gather(
        client.post("/api/course-visits", headers=headers, json=payload),
        client.post("/api/course-visits", headers=headers, json=payload),
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]


@pytest.mark.asyncio
async def test_course_visit_groups_lesson_sessions(client):
    teacher_email = f"visit-t-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_email = f"visit-s-{uuid.uuid4().hex[:8]}@example.com"
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    token = await login(client, student_email)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/api/course-visits",
        headers=headers,
        json={"enrollmentId": ids["enrollment_id"], "visitKey": "tab-1"},
    )
    assert created.status_code == 201, created.text
    visit_id = created.json()["id"]

    first = await client.post(
        "/api/learning-sessions",
        headers=headers,
        json=_session_payload(ids["enrollment_id"], ids["lesson_id"], visit_id),
    )
    assert first.status_code == 201, first.text
    assert first.json()["courseVisitId"] == visit_id

    ended = await client.patch(
        f"/api/learning-sessions/{first.json()['id']}",
        headers=headers,
        json={"status": "completed"},
    )
    assert ended.status_code == 200, ended.text

    second = await client.post(
        "/api/learning-sessions",
        headers=headers,
        json=_session_payload(ids["enrollment_id"], ids["lesson_id"], visit_id),
    )
    assert second.status_code == 201, second.text
    assert second.json()["courseVisitId"] == visit_id

    # Idempotent theo visitKey.
    again = await client.post(
        "/api/course-visits",
        headers=headers,
        json={"enrollmentId": ids["enrollment_id"], "visitKey": "tab-1"},
    )
    assert again.status_code == 201
    assert again.json()["id"] == visit_id

    async with SessionLocal() as db:
        assert (
            await db.execute(
                select(func.count()).select_from(CourseVisit).where(
                    CourseVisit.enrollment_id == ids["enrollment_id"]
                )
            )
        ).scalar_one() == 1
        assert (
            await db.execute(
                select(func.count()).select_from(LearningSession).where(
                    LearningSession.course_visit_id == visit_id
                )
            )
        ).scalar_one() == 2

    teacher_token = await login(client, teacher_email)
    rows = await client.get(
        f"/teacher/courses/{ids['course_id']}/visits",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert rows.status_code == 200, rows.text
    assert len(rows.json()) == 1
    assert rows.json()[0]["id"] == visit_id
    assert rows.json()[0]["lessonSessionCount"] == 2

    by_student = await client.get(
        f"/teacher/students/{student_id}/visits",
        params={"courseId": ids["course_id"]},
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert by_student.status_code == 200, by_student.text
    assert by_student.json()[0]["id"] == visit_id

    summary = await client.get(
        f"/teacher/visits/{visit_id}/summary",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["lessonSessionCount"] == 2

    export = await client.get(
        f"/teacher/visits/{visit_id}/export",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert export.status_code == 200, export.text
    first_line = export.text.splitlines()[0]
    assert '"type": "manifest"' in first_line
    assert visit_id in first_line
