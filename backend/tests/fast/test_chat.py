"""Chat proxy: access gate, SSE, persistence, session CRUD."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from tests.conftest import (
    create_course,
    create_lesson,
    create_quiz,
    create_user,
    fetch_all,
    fetch_one,
    login,
)

pytestmark = pytest.mark.fast

SSE_OK = (
    'event: token\ndata: {"text":"Xin chào "}\n\n'
    'event: token\ndata: {"text":"bạn"}\n\n'
    'event: citations\ndata: {"citations":[{"documentId":"d1","title":"Bài 1",'
    '"location":"","snippet":"","score":0.5}]}\n\n'
    'event: done\ndata: {"intent":"course_qa","verified":true,'
    '"routes":["knowledge"],"finish_reason":"stop","citation_count":1}\n\n'
)


def _events(text: str) -> list[tuple[str, dict]]:
    events = []
    event = None
    for line in text.splitlines():
        if line.startswith("event: "):
            event = line[7:]
        elif line.startswith("data: ") and event:
            events.append((event, json.loads(line[6:])))
    return events


async def _chat_fixture(client, *, allow_chatbot=True):
    teacher = await create_user(role="teacher", email="t-chat@example.com")
    student = await create_user(email="s-chat@example.com")
    ids = await create_course(
        teacher_id=teacher["id"],
        student_id=student["id"],
        status="published",
        require_calibration=False,
    )
    lesson_id = await create_lesson(module_id=ids["module_id"])
    quiz_id = None
    if not allow_chatbot:
        quiz_id = await create_quiz(
            module_id=ids["module_id"],
            allow_chatbot=False,
            position=1,
        )
    await login(client, student["email"])
    return teacher, student, ids, lesson_id, quiz_id


@respx.mock
async def test_chat_stream_forwards_sse_and_persists(client):
    _, _, ids, lesson_id, _ = await _chat_fixture(client)
    respx.post("http://chatbot:8000/chat/stream").mock(
        return_value=httpx.Response(200, text=SSE_OK)
    )

    access = await client.get(f"/api/courses/{ids['course_id']}/chat/access")
    assert access.status_code == 200
    assert access.json()["allowed"] is True

    response = await client.post(
        f"/api/courses/{ids['course_id']}/chat/stream",
        json={"message": "Giải thích bài này", "lessonId": lesson_id},
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _events(response.text)
    names = [name for name, _ in events]
    assert names[0] == "session"
    assert "token" in names
    assert "citations" in names
    assert names[-1] == "done"

    message_rows = await fetch_all(
        "SELECT role, content, intent FROM chat_messages ORDER BY created_at"
    )
    assert [row["role"] for row in message_rows] == ["student", "assistant"]
    assert message_rows[0]["content"] == "Giải thích bài này"
    assert message_rows[1]["content"] == "Xin chào bạn"
    assert message_rows[1]["intent"] == "course_qa"

    sessions = await client.get(f"/api/courses/{ids['course_id']}/chat/sessions")
    assert sessions.status_code == 200
    [session] = sessions.json()
    assert session["messageCount"] == 2
    assert session["canContinue"] is True

    messages = await client.get(f"/api/chat/sessions/{session['id']}/messages")
    assert messages.status_code == 200
    assert len(messages.json()) == 2

    renamed = await client.patch(
        f"/api/chat/sessions/{session['id']}", json={"title": "Phiên mới"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Phiên mới"

    deleted = await client.delete(f"/api/chat/sessions/{session['id']}")
    assert deleted.status_code == 200
    assert await fetch_one("SELECT id FROM chat_sessions") is None
    assert await fetch_all("SELECT id FROM chat_messages") == []


@respx.mock
async def test_chat_access_blocked_by_quiz(client):
    _, _, ids, _lesson_id, quiz_id = await _chat_fixture(
        client, allow_chatbot=False
    )
    await client.post(f"/api/lessons/{quiz_id}/attempts")
    access = await client.get(f"/api/courses/{ids['course_id']}/chat/access")
    assert access.status_code == 200
    body = access.json()
    assert body["allowed"] is False
    assert body["blockedUntil"]

    response = await client.post(
        f"/api/courses/{ids['course_id']}/chat/stream",
        json={"message": "Gợi ý", "assignmentId": quiz_id},
    )
    assert response.status_code == 403


@respx.mock
async def test_chat_stream_error_is_sse_event(client):
    _, _, ids, _, _ = await _chat_fixture(client)
    respx.post("http://chatbot:8000/chat/stream").mock(
        return_value=httpx.Response(500, text="boom")
    )
    response = await client.post(
        f"/api/courses/{ids['course_id']}/chat/stream",
        json={"message": "Hỏi"},
    )
    assert response.status_code == 200
    events = _events(response.text)
    assert any(name == "error" for name, _ in events)


async def test_chat_without_configuration_returns_error_stream(client):
    from app.core.config import settings

    _, _, ids, _, _ = await _chat_fixture(client)
    original = settings.chatbot_internal_token
    settings.chatbot_internal_token = ""
    try:
        response = await client.post(
            f"/api/courses/{ids['course_id']}/chat/stream",
            json={"message": "Hỏi"},
        )
    finally:
        settings.chatbot_internal_token = original
    assert response.status_code == 200
    events = _events(response.text)
    assert events[0][0] == "error"
    assert "chưa được cấu hình" in events[0][1]["message"]
