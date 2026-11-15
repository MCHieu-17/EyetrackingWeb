"""Contract tests: request schema -> ChatState và hai endpoint /chat."""

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import chat as chat_api
from app.schemas import ChatRequest


def _request(**overrides) -> ChatRequest:
    values = {
        "message": "Gợi ý cho em",
        "course_id": "course-1",
        "thread_id": "thread-1",
        "lesson_id": "lesson-1",
        "attempt_id": "attempt-1",
        "assignment_id": "assignment-1",
        "assignment_title": "Bài tập 1",
        "support_mode": "hint",
    }
    values.update(overrides)
    return ChatRequest(**values)


def test_state_from_request_maps_assignment_and_attempt():
    state = chat_api._state_from_request(_request())

    assert state.assignment_id == "assignment-1"
    assert state.attempt_id == "attempt-1"


def test_state_from_request_keeps_attempt_without_assignment():
    state = chat_api._state_from_request(_request(assignment_id=None))

    assert state.assignment_id is None
    assert state.attempt_id == "attempt-1"


def test_chat_and_stream_accept_assignment_context(monkeypatch):
    seen: dict[str, object] = {}

    async def fake_collect(state):
        seen["chat"] = state
        return "Trả lời", [], "course_qa", True

    async def fake_run(state):
        seen["stream"] = state
        yield {"event": "token", "data": {"text": "Trả lời"}}
        yield {
            "event": "done",
            "data": {
                "intent": "course_qa",
                "verified": True,
                "finish_reason": "stop",
            },
        }

    monkeypatch.setattr(chat_api, "collect_chat", fake_collect)
    monkeypatch.setattr(chat_api, "run_chat", fake_run)
    monkeypatch.setattr(chat_api, "internal_token", lambda: "test-token")
    monkeypatch.setattr(chat_api, "_chat_slots", asyncio.Semaphore(1))

    app = FastAPI()
    app.include_router(chat_api.router)
    payload = _request().model_dump()
    headers = {"X-Chatbot-Token": "test-token"}

    with TestClient(app) as client:
        response = client.post("/chat", json=payload, headers=headers)
        assert response.status_code == 200, response.text
        assert seen["chat"].assignment_id == "assignment-1"
        assert seen["chat"].attempt_id == "attempt-1"

        streamed = client.post("/chat/stream", json=payload, headers=headers)
        assert streamed.status_code == 200, streamed.text
        assert "event: token" in streamed.text
        assert seen["stream"].assignment_id == "assignment-1"
        assert seen["stream"].attempt_id == "attempt-1"
