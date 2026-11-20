"""Maintenance: expire session/visit, xoá OTP/gaze cũ."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from app.maintenance import run_maintenance
from tests.conftest import (
    create_course,
    create_lesson,
    create_slide,
    create_user,
    execute,
    fetch_one,
    now,
)

pytestmark = pytest.mark.fast


async def test_maintenance_expires_sessions_and_visits():
    teacher = await create_user(role="teacher", email="t-maint@example.com")
    student = await create_user(email="s-maint@example.com")
    ids = await create_course(
        teacher_id=teacher["id"], student_id=student["id"]
    )
    lesson_id = await create_lesson(module_id=ids["module_id"])
    slide_id = await create_slide(lesson_id=lesson_id)

    visit_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    view_id = str(uuid.uuid4())
    await execute(
        "INSERT INTO course_visits "
        "(id, enrollment_id, started_at, last_seen_at, status) "
        "VALUES (:id, :enrollment, :old, :old, 'active')",
        {
            "id": visit_id,
            "enrollment": ids["enrollment_id"],
            "old": now() - timedelta(minutes=45),
        },
    )
    await execute(
        "INSERT INTO learning_sessions "
        "(id, enrollment_id, lesson_id, course_visit_id, status, "
        " started_at, expires_at) "
        "VALUES (:id, :enrollment, :lesson, :visit, 'in_progress', "
        "        :started, :expired)",
        {
            "id": session_id,
            "enrollment": ids["enrollment_id"],
            "lesson": lesson_id,
            "visit": visit_id,
            "started": now() - timedelta(hours=1),
            "expired": now() - timedelta(minutes=10),
        },
    )
    await execute(
        "INSERT INTO content_views "
        "(id, session_id, slide_id, surface, sequence_no, started_at, "
        " analysis_status) "
        "VALUES (:id, :session, :slide, 'lesson', 0, :started, 'pending')",
        {
            "id": view_id,
            "session": session_id,
            "slide": slide_id,
            "started": now() - timedelta(minutes=20),
        },
    )

    counts = await run_maintenance()

    assert counts["learning_sessions_expired"] >= 1
    assert counts["course_visits_expired"] >= 1
    session = await fetch_one(
        "SELECT status, ended_at FROM learning_sessions WHERE id = :id",
        {"id": session_id},
    )
    assert session["status"] == "expired"
    assert session["ended_at"] is not None
    view = await fetch_one(
        "SELECT ended_at FROM content_views WHERE id = :id", {"id": view_id}
    )
    assert view["ended_at"] is not None
    visit = await fetch_one(
        "SELECT status FROM course_visits WHERE id = :id", {"id": visit_id}
    )
    assert visit["status"] == "expired"
    job = await fetch_one(
        "SELECT kind, status FROM background_jobs WHERE lesson_id = :id",
        {"id": lesson_id},
    )
    assert job["kind"] == "analyze_lesson"
    assert job["status"] == "queued"


async def test_maintenance_deletes_expired_otp_and_old_gaze():
    student = await create_user(email="s-maint-clean@example.com")
    teacher = await create_user(role="teacher", email="t-maint-clean@example.com")
    ids = await create_course(
        teacher_id=teacher["id"], student_id=student["id"]
    )
    lesson_id = await create_lesson(module_id=ids["module_id"])
    slide_id = await create_slide(lesson_id=lesson_id)

    otp_id = str(uuid.uuid4())
    await execute(
        "INSERT INTO email_otps "
        "(id, email, code_hash, expires_at, attempts, max_attempts) "
        "VALUES (:id, '99999999@st.neu.edu.vn', :hash, :expires, 0, 5)",
        {
            "id": otp_id,
            "hash": uuid.uuid4().hex + uuid.uuid4().hex,
            "expires": now() - timedelta(days=2),
        },
    )
    session_id = str(uuid.uuid4())
    view_id = str(uuid.uuid4())
    await execute(
        "INSERT INTO learning_sessions "
        "(id, enrollment_id, lesson_id, status, started_at, expires_at) "
        "VALUES (:id, :enrollment, :lesson, 'completed', :started, :expires)",
        {
            "id": session_id,
            "enrollment": ids["enrollment_id"],
            "lesson": lesson_id,
            "started": now() - timedelta(days=400),
            "expires": now() + timedelta(hours=1),
        },
    )
    await execute(
        "INSERT INTO content_views "
        "(id, session_id, slide_id, surface, sequence_no, started_at) "
        "VALUES (:id, :session, :slide, 'lesson', 0, :started)",
        {
            "id": view_id,
            "session": session_id,
            "slide": slide_id,
            "started": now() - timedelta(days=400),
        },
    )
    await execute(
        "INSERT INTO gaze_samples "
        "(content_view_id, client_batch_id, sequence, event_time, "
        " viewport_x, viewport_y, status) "
        "VALUES (:view, :batch, 0, :event_time, 0.5, 0.5, 'ok')",
        {
            "view": view_id,
            "batch": str(uuid.uuid4()),
            "event_time": now() - timedelta(days=400),
        },
    )

    counts = await run_maintenance()

    assert counts["email_otps_deleted"] >= 1
    assert counts["gaze_samples_deleted"] >= 1
    assert await fetch_one(
        "SELECT id FROM email_otps WHERE id = :id", {"id": otp_id}
    ) is None
    assert await fetch_one(
        "SELECT id FROM gaze_samples WHERE content_view_id = :id",
        {"id": view_id},
    ) is None
