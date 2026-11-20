"""Smoke khép kín: backend upload → ingest thật → chat thật → cleanup.

Chỉ chạy khi stack đang chạy và có SMOKE_BACKEND_URL. Test dùng API backend
(cùng chatbot/LLM thật), không import app chatbot.
"""

from __future__ import annotations

import json
import os
import time
import uuid

import httpx
import psycopg
import pymupdf
import pytest

pytestmark = [pytest.mark.smoke]

BACKEND = os.getenv("SMOKE_BACKEND_URL", "")
DB_URL = os.getenv("SMOKE_DATABASE_URL", "")
PASSWORD = os.getenv("SMOKE_PASSWORD", "Password123!")
TEACHER = os.getenv("SMOKE_TEACHER", "teacher@school.edu.vn")
STUDENT = os.getenv("SMOKE_STUDENT", "student@school.edu.vn")


def _pdf_bytes(marker: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 120), f"GazeEdu smoke {marker}", fontsize=28)
    page.insert_text((72, 170), "Đây là nội dung kiểm tra RAG.", fontsize=20)
    data = doc.tobytes()
    doc.close()
    return data


def _events(text: str):
    event = None
    for line in text.splitlines():
        if line.startswith("event: "):
            event = line[7:]
        elif line.startswith("data: ") and event:
            yield event, json.loads(line[6:])


def _login(client: httpx.Client, email: str) -> str:
    response = client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response.json()["accessToken"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_rag_smoke_closed_loop():
    if not BACKEND:
        pytest.skip("thiếu SMOKE_BACKEND_URL (stack thật)")
    marker = f"marker-{uuid.uuid4().hex[:8]}"
    client = httpx.Client(base_url=BACKEND, timeout=180)
    course_id = None
    teacher = {}
    try:
        teacher_token = _login(client, TEACHER)
        teacher = _auth(teacher_token)
        created = client.post(
            "/teacher/courses",
            headers=teacher,
            json={"title": f"E2E Smoke {marker}", "requireCalibration": False},
        )
        assert created.status_code == 201, created.text
        course_id = created.json()["id"]

        module = client.post(
            f"/teacher/courses/{course_id}/modules",
            headers=teacher,
            json={"title": "Chương smoke"},
        )
        assert module.status_code == 201, module.text
        module_id = module.json()["id"]

        lesson = client.post(
            f"/teacher/modules/{module_id}/lessons",
            headers=teacher,
            json={"title": "Bài smoke"},
        )
        assert lesson.status_code == 201, lesson.text
        lesson_id = lesson.json()["id"]

        upload = client.post(
            f"/teacher/lessons/{lesson_id}/slides/upload",
            headers=teacher,
            files={
                "file": (
                    "smoke.pdf",
                    _pdf_bytes(marker),
                    "application/pdf",
                )
            },
        )
        assert upload.status_code == 202, upload.text

        deadline = time.time() + 180
        slides = []
        while time.time() < deadline:
            listing = client.get(
                f"/teacher/lessons/{lesson_id}/slides", headers=teacher
            )
            assert listing.status_code == 200, listing.text
            slides = listing.json()
            if slides and all(
                slide["embeddingStatus"] == "ready" for slide in slides
            ):
                break
            time.sleep(3)
        else:
            pytest.fail(f"index chưa xong sau 180s: {slides}")

        published = client.post(
            f"/teacher/courses/{course_id}/publish", headers=teacher
        )
        assert published.status_code == 200, published.text

        directory = client.get("/teacher/students", headers=teacher)
        assert directory.status_code == 200
        student = next(
            item
            for item in directory.json()
            if item["email"] == STUDENT
        )
        enrolled = client.post(
            f"/teacher/courses/{course_id}/students",
            headers=teacher,
            json={"studentIds": [student["id"]]},
        )
        assert enrolled.status_code == 201, enrolled.text

        student_token = _auth(_login(client, STUDENT))
        question = f"{marker} là gì?"
        response = client.post(
            f"/api/courses/{course_id}/chat/stream",
            headers=student_token,
            json={"message": question},
        )
        assert response.status_code == 200, response.text
        events = list(_events(response.text))
        assert any(name == "token" for name, _ in events), response.text
        citations = [
            data for name, data in events if name == "citations"
        ]
        assert citations, response.text
        citations = citations[0]
        assert citations["citations"], response.text
        assert any(
            (citation.get("slideId") or citation.get("slide_id")) in {slide["id"] for slide in slides}
            for citation in citations["citations"]
        )

        sessions = client.get(
            f"/api/courses/{course_id}/chat/sessions", headers=student_token
        )
        assert sessions.status_code == 200
        assert sessions.json()
        messages = client.get(
            f"/api/chat/sessions/{sessions.json()[0]['id']}/messages",
            headers=student_token,
        )
        assert messages.status_code == 200
        assert len(messages.json()) >= 2
    finally:
        if course_id:
            client.delete(f"/teacher/courses/{course_id}", headers=teacher)
        client.close()

    if DB_URL:
        with psycopg.connect(DB_URL) as conn:
            count = conn.execute(
                "SELECT count(*) FROM v_chatbot_slide_documents "
                "WHERE course_id = %s",
                (course_id,),
            ).fetchone()[0]
        assert count == 0
