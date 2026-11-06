"""Phase 2 smoke: draft → upload PDF → publish → student reads published."""

from __future__ import annotations

import asyncio

import pymupdf
import pytest

from tests.conftest import auth, login, make_user


def _pdf_bytes() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Phase 2 slide")
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture()
def teacher(client):
    asyncio.run(make_user("teacher2@example.com", "teacher", full_name="GV Phase 2"))
    return login(client, "teacher2@example.com")


@pytest.fixture()
def student(client):
    asyncio.run(make_user("student2@example.com", "student", full_name="SV Phase 2"))
    return login(client, "student2@example.com")


def test_content_draft_publish_and_student_read(client, teacher, student):
    headers = auth(teacher)

    created = client.post(
        "/teacher/courses",
        json={"title": "Khóa Phase 2", "description": "Mô tả"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    course_id = created.json()["id"]

    module = client.post(
        f"/teacher/courses/{course_id}/modules",
        json={"title": "Chương 1"},
        headers=headers,
    )
    assert module.status_code == 201, module.text
    module_id = module.json()["id"]

    lesson = client.post(
        f"/teacher/modules/{module_id}/lessons",
        json={"title": "Bài 1"},
        headers=headers,
    )
    assert lesson.status_code == 201, lesson.text
    lesson_id = lesson.json()["id"]

    upload = client.post(
        f"/teacher/lessons/{lesson_id}/slides/upload",
        files={"pdf": ("phase2.pdf", _pdf_bytes(), "application/pdf")},
        headers=headers,
    )
    assert upload.status_code == 201, upload.text
    assert upload.json()["slides"] == 1

    slides = client.get(
        f"/teacher/lessons/{lesson_id}/slides", headers=headers
    )
    assert slides.status_code == 200, slides.text
    assert len(slides.json()) == 1
    slide = slides.json()[0]
    assert slide["imageUrl"].startswith("/media/assets/")

    tree = client.get(f"/teacher/courses/{course_id}", headers=headers)
    assert tree.status_code == 200, tree.text
    assert tree.json()[0]["lessons"][0]["slides"] == 1
    lesson_version_id = tree.json()[0]["lessons"][0]["lessonVersionId"]

    published = client.post(
        f"/teacher/courses/{course_id}/publish",
        json={},
        headers=headers,
    )
    assert published.status_code == 200, published.text
    assert published.json()["courseVersionId"]

    async def _published_state():
        from sqlalchemy import text

        from app.db.session import SessionLocal

        async with SessionLocal() as db:
            state = (
                await db.execute(
                    text("SELECT state FROM lesson_versions WHERE id = :id"),
                    {"id": lesson_version_id},
                )
            ).scalar_one()
            view_count = (
                await db.execute(
                    text(
                        "SELECT count(*) FROM v_published_course_outline "
                        "WHERE course_id = :id"
                    ),
                    {"id": course_id},
                )
            ).scalar_one()
            return state, view_count

    state, view_count = asyncio.run(_published_state())
    assert state == "published"
    assert view_count == 1

    outline = client.get(f"/api/courses/{course_id}", headers=auth(student))
    assert outline.status_code == 200, outline.text
    body = outline.json()
    assert body["title"] == "Khóa Phase 2"
    assert body["modules"][0]["lessons"][0]["slideCount"] == 1

    enroll = client.post(f"/api/courses/{course_id}/enroll", headers=auth(student))
    assert enroll.status_code == 201, enroll.text

    enrollments = client.get("/api/me/enrollments", headers=auth(student))
    assert enrollments.status_code == 200, enrollments.text
    assert enrollments.json()[0]["course"]["title"] == "Khóa Phase 2"

    contents = client.get(
        f"/api/lessons/{lesson_id}/contents", headers=auth(student)
    )
    assert contents.status_code == 200, contents.text
    assert len(contents.json()) == 1
    image_url = contents.json()[0]["imageUrl"]
    assert image_url.startswith("/media/assets/")

    media = client.get(image_url, headers=auth(student))
    assert media.status_code == 200, media.text
    assert media.headers["content-type"].startswith("image/jpeg")


def test_publish_rejects_empty_lesson(client, teacher):
    headers = auth(teacher)
    created = client.post(
        "/teacher/courses",
        json={"title": "Khóa rỗng"},
        headers=headers,
    )
    course_id = created.json()["id"]
    module = client.post(
        f"/teacher/courses/{course_id}/modules",
        json={"title": "Chương"},
        headers=headers,
    )
    module_id = module.json()["id"]
    client.post(
        f"/teacher/modules/{module_id}/lessons",
        json={"title": "Bài chưa có slide"},
        headers=headers,
    )
    published = client.post(
        f"/teacher/courses/{course_id}/publish", json={}, headers=headers
    )
    assert published.status_code == 400
    assert published.json()["detail"]["code"] == "content_invalid"
