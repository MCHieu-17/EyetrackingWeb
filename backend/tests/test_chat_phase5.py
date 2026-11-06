"""Phase 5: chat context theo course/lesson version và attempt cụ thể."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal
from app.services import study_chat
from tests.conftest import auth, login, make_user


@pytest.fixture()
def teacher(client):
    asyncio.run(make_user("teacher-chat5@example.com", "teacher", full_name="GV Chat"))
    return login(client, "teacher-chat5@example.com")


@pytest.fixture()
def student(client):
    asyncio.run(make_user("student-chat5@example.com", "student", full_name="SV Chat"))
    return login(client, "student-chat5@example.com")


def _published_quiz(client, teacher):
    headers = auth(teacher)
    course = client.post(
        "/teacher/courses", json={"title": "Khóa Chat"}, headers=headers
    ).json()
    module = client.post(
        f"/teacher/courses/{course['id']}/modules",
        json={"title": "Chương"},
        headers=headers,
    ).json()
    quiz = client.post(
        f"/teacher/modules/{module['id']}/quizzes",
        json={"title": "Bài tập", "durationMinutes": 15},
        headers=headers,
    ).json()
    quiz_id = quiz["quizId"]
    lesson_id = quiz["id"]
    patched = client.patch(
        f"/api/teacher/quiz-specs/{quiz_id}",
        json={
            "allowRetry": True,
            "allowChatbot": True,
            "questions": [
                {
                    "id": "q1",
                    "prompt": "2 + 2 = ?",
                    "options": [
                        {"id": "a", "text": "4"},
                        {"id": "b", "text": "5"},
                    ],
                    "correctOptionIds": ["a"],
                    "allowMultiple": False,
                    "explanation": "4",
                    "points": 2,
                }
            ],
        },
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    published = client.post(
        f"/teacher/courses/{course['id']}/publish", json={}, headers=headers
    )
    assert published.status_code == 200, published.text
    return course["id"], lesson_id, quiz_id


def _context_key(session_id: str) -> str:
    async def load():
        async with SessionLocal() as db:
            return (
                await db.execute(
                    text("SELECT context_key FROM chat_sessions WHERE id = :id"),
                    {"id": session_id},
                )
            ).scalar_one()

    return asyncio.run(load())


def test_chat_attempt_specific_hint_review_and_internal_lms(client, teacher, student):
    course_id, lesson_id, quiz_id = _published_quiz(client, teacher)
    student_headers = auth(student)
    enroll = client.post(f"/api/courses/{course_id}/enroll", headers=student_headers)
    assert enroll.status_code == 201, enroll.text

    started = client.post(
        f"/api/lessons/{lesson_id}/attempts", headers=student_headers
    )
    assert started.status_code == 201, started.text
    attempt_id = started.json()["id"]

    access = client.get(
        f"/api/courses/{course_id}/chat/access", headers=student_headers
    )
    assert access.status_code == 200, access.text
    assert access.json()["allowed"] is True

    captured: dict = {}

    async def fake_ask(payload):
        captured.update(payload)
        return {
            "answer": "Gợi ý: hãy đọc lại phép cộng.",
            "citations": [],
            "intent": "exercise_hints",
            "verified": True,
        }

    original = study_chat._ask_chatbot
    study_chat._ask_chatbot = fake_ask
    try:
        hints = client.post(
            f"/api/courses/{course_id}/chat",
            headers=student_headers,
            json={
                "message": "Cho mình đáp án câu 1",
                "assignmentId": quiz_id,
                "attemptId": attempt_id,
            },
        )
        assert hints.status_code == 200, hints.text
        assert captured["support_mode"] == "hint"
        assert captured["course_version_id"]
        assert captured["lesson_version_id"] == quiz_id
        assert captured["attempt_id"] == attempt_id
        assert "Đáp án đúng" not in captured["assignment_context"]

        submitted = client.post(
            f"/api/attempts/{attempt_id}/submit",
            json={"answers": {"q1": ["a"]}},
            headers=student_headers,
        )
        assert submitted.status_code == 200, submitted.text

        review = client.post(
            f"/api/courses/{course_id}/chat",
            headers=student_headers,
            json={
                "message": "Vì sao đúng?",
                "assignmentId": quiz_id,
                "attemptId": attempt_id,
            },
        )
        assert review.status_code == 200, review.text
        assert captured["support_mode"] == "review"
        assert "Đáp án đúng" in captured["assignment_context"]
        review_session_id = review.json()["sessionId"]
        review_context_key = _context_key(review_session_id)

        # Internal LMS query dùng đúng session/context và attempt.
        internal = client.post(
            "/internal/chat/lms-query",
            headers={"X-Chatbot-Token": settings.chatbot_internal_token},
            json={
                "session_id": review_session_id,
                "context_key": review_context_key,
                "operation": "assignments",
                "target": "",
            },
        )
        assert internal.status_code == 200, internal.text
        assignments = internal.json()["assignments"]
        assert assignments[0]["id"] == quiz_id
        assert assignments[0]["status"] in {"đã nộp", "đang làm"}

        results = client.post(
            "/internal/chat/lms-query",
            headers={"X-Chatbot-Token": settings.chatbot_internal_token},
            json={
                "session_id": review_session_id,
                "context_key": review_context_key,
                "operation": "results",
                "target": quiz_id,
            },
        )
        assert results.status_code == 200, results.text
        assert results.json()["assignments"][0]["score"] == 2
        # Retry tạo attempt mới: attempt mới là hint, attempt cũ vẫn review.
        retried = client.post(
            f"/api/attempts/{attempt_id}/retry", headers=student_headers
        )
        assert retried.status_code == 201, retried.text
        new_attempt_id = retried.json()["id"]
        new_hint = client.post(
            f"/api/courses/{course_id}/chat",
            headers=student_headers,
            json={
                "message": "Gợi ý câu 1",
                "assignmentId": quiz_id,
                "attemptId": new_attempt_id,
            },
        )
        assert new_hint.status_code == 200, new_hint.text
        assert captured["support_mode"] == "hint"
        assert captured["attempt_id"] == new_attempt_id

        old_review = client.post(
            f"/api/courses/{course_id}/chat",
            headers=student_headers,
            json={
                "message": "Chữa bài cũ",
                "assignmentId": quiz_id,
                "attemptId": attempt_id,
            },
        )
        assert old_review.status_code == 200, old_review.text
        assert captured["support_mode"] == "review"
        assert captured["attempt_id"] == attempt_id

    finally:
        study_chat._ask_chatbot = original


def test_chat_access_blocks_when_quiz_disallows_chatbot(client, teacher, student):
    headers = auth(teacher)
    course = client.post(
        "/teacher/courses", json={"title": "Khóa Chat Block"}, headers=headers
    ).json()
    module = client.post(
        f"/teacher/courses/{course['id']}/modules",
        json={"title": "Chương"},
        headers=headers,
    ).json()
    quiz = client.post(
        f"/teacher/modules/{module['id']}/quizzes",
        json={"title": "Bài tập khóa chat", "durationMinutes": 15},
        headers=headers,
    ).json()
    quiz_id = quiz["quizId"]
    patched = client.patch(
        f"/api/teacher/quiz-specs/{quiz_id}",
        json={
            "allowChatbot": False,
            "questions": [
                {
                    "id": "q1",
                    "prompt": "1 + 1 = ?",
                    "options": [
                        {"id": "a", "text": "2"},
                        {"id": "b", "text": "3"},
                    ],
                    "correctOptionIds": ["a"],
                    "allowMultiple": False,
                    "explanation": "2",
                    "points": 1,
                }
            ],
        },
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    published = client.post(
        f"/teacher/courses/{course['id']}/publish", json={}, headers=headers
    )
    assert published.status_code == 200, published.text

    student_headers = auth(student)
    enroll = client.post(
        f"/api/courses/{course['id']}/enroll", headers=student_headers
    )
    assert enroll.status_code == 201, enroll.text
    started = client.post(
        f"/api/lessons/{quiz['id']}/attempts", headers=student_headers
    )
    assert started.status_code == 201, started.text

    access = client.get(
        f"/api/courses/{course['id']}/chat/access", headers=student_headers
    )
    assert access.status_code == 200, access.text
    assert access.json()["allowed"] is False
    assert access.json()["blockedUntil"]
