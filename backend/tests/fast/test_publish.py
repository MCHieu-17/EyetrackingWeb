"""Khóa validation publish và side effect lên background_jobs."""

from __future__ import annotations

import pytest

from tests.conftest import (
    create_course,
    create_lesson,
    create_media_asset,
    create_quiz,
    create_slide,
    create_user,
    execute,
    fetch_one,
    login,
)

pytestmark = pytest.mark.fast


async def _teacher_course(client, *, title="Publish"):
    teacher = await create_user(role="teacher", email=f"{title.lower()}@example.com")
    ids = await create_course(teacher_id=teacher["id"], title=title)
    await login(client, teacher["email"])
    return teacher, ids


async def _ready_lesson(ids, *, index_status="ready", asset_state="ready"):
    asset_id = await create_media_asset(course_id=ids["course_id"])
    lesson_id = await create_lesson(
        module_id=ids["module_id"], pdf_asset_id=asset_id
    )
    await create_slide(lesson_id=lesson_id, index_status=index_status)
    await execute(
        "UPDATE lessons SET pdf_asset_id = :asset WHERE id = :lesson",
        {"asset": asset_id, "lesson": lesson_id},
    )
    await execute(
        "UPDATE media_assets SET state = :state WHERE id = :id",
        {"state": asset_state, "id": asset_id},
    )
    return lesson_id, asset_id


async def test_publish_requires_modules_and_lessons(client):
    teacher = await create_user(role="teacher", email="pub-empty@example.com")
    ids = await create_course(teacher_id=teacher["id"])
    await login(client, teacher["email"])
    response = await client.post(f"/teacher/courses/{ids['course_id']}/publish")
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "content_invalid"

    await create_lesson(module_id=ids["module_id"])
    no_slides = await client.post(f"/teacher/courses/{ids['course_id']}/publish")
    assert no_slides.status_code == 400
    assert "chưa có slide" in no_slides.json()["detail"]["message"]


async def test_publish_blocks_pending_index_and_enqueues_job(client):
    _teacher, ids = await _teacher_course(client, title="Pending")
    lesson_id, _ = await _ready_lesson(ids, index_status="pending")

    response = await client.post(f"/teacher/courses/{ids['course_id']}/publish")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "slides_not_indexed"
    job = await fetch_one(
        "SELECT kind, status FROM background_jobs "
        "WHERE lesson_id = :lesson ORDER BY created_at DESC LIMIT 1",
        {"lesson": lesson_id},
    )
    assert job["kind"] == "index_slides"
    assert job["status"] == "queued"


async def test_publish_blocks_unready_media(client):
    _teacher, ids = await _teacher_course(client, title="Media")
    await _ready_lesson(ids, asset_state="staging")
    response = await client.post(f"/teacher/courses/{ids['course_id']}/publish")
    assert response.status_code == 400
    assert "chưa sẵn sàng" in response.json()["detail"]["message"]


async def test_publish_blocks_invalid_quiz(client):
    _teacher, ids = await _teacher_course(client, title="Quizbad")
    await create_quiz(module_id=ids["module_id"], questions=[])
    response = await client.post(f"/teacher/courses/{ids['course_id']}/publish")
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "quiz_not_ready"


async def test_publish_success_and_outline(client, client_factory):
    teacher = await create_user(role="teacher", email="pub-ok@example.com")
    student = await create_user(email="pub-student@example.com")
    ids = await create_course(
        teacher_id=teacher["id"], student_id=student["id"], title="Published OK"
    )
    await login(client, teacher["email"])
    _, _ = await _ready_lesson(ids)

    published = await client.post(f"/teacher/courses/{ids['course_id']}/publish")
    assert published.status_code == 200, published.text
    course = await fetch_one(
        "SELECT status, published_at FROM courses WHERE id = :id",
        {"id": ids["course_id"]},
    )
    assert course["status"] == "published"
    assert course["published_at"] is not None

    student_client = await client_factory()
    await login(student_client, student["email"])
    outline = await student_client.get(f"/api/courses/{ids['course_id']}")
    assert outline.status_code == 200
    assert outline.json()["id"] == ids["course_id"]


async def test_quiz_publish_patch_rolls_back_when_course_invalid(client):
    _teacher, ids = await _teacher_course(client, title="Quizpatch")
    await create_lesson(module_id=ids["module_id"], title="Bài thiếu slide")
    quiz_id = await create_quiz(
        module_id=ids["module_id"], position=1, status="draft"
    )

    response = await client.patch(
        f"/teacher/lessons/{quiz_id}/quiz",
        json={"status": "published"},
    )
    assert response.status_code == 400
    row = await fetch_one(
        "SELECT quiz_config FROM lessons WHERE id = :id", {"id": quiz_id}
    )
    assert row["quiz_config"]["status"] == "draft"


async def test_quiz_publish_patch_succeeds_when_course_valid(client):
    _teacher, ids = await _teacher_course(client, title="Quizok")
    await _ready_lesson(ids)
    quiz_id = await create_quiz(
        module_id=ids["module_id"], position=1, status="draft"
    )

    response = await client.patch(
        f"/teacher/lessons/{quiz_id}/quiz",
        json={"status": "published"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "published"
    course = await fetch_one(
        "SELECT status FROM courses WHERE id = :id", {"id": ids["course_id"]}
    )
    assert course["status"] == "published"
