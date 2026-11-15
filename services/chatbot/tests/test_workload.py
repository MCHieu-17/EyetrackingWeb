"""Tests cho ưu tiên chat so với ingest và vòng đời SSE."""

import asyncio
import threading

import pytest
from fastapi import HTTPException

from app.api import chat as chat_api
from app.schemas import ChatRequest
from app.workflow import workload


@pytest.fixture(autouse=True)
def reset_chat_priority():
    workload._active_chats = 0
    yield
    workload._active_chats = 0


def _payload() -> ChatRequest:
    return ChatRequest(message="Câu hỏi", course_id="course-1", thread_id="thread-1")


def test_chat_endpoint_tracks_active_chat(monkeypatch):
    seen: list[int] = []

    async def fake_collect(state):
        seen.append(workload._active_chats)
        return "answer", [], "course_qa", True

    monkeypatch.setattr(chat_api, "collect_chat", fake_collect)

    response = asyncio.run(chat_api.chat(_payload()))

    assert response.answer == "answer"
    assert seen == [1]
    assert workload._active_chats == 0


def test_chat_endpoint_releases_priority_on_error(monkeypatch):
    async def failing_collect(state):
        raise RuntimeError("pipeline lỗi")

    monkeypatch.setattr(chat_api, "collect_chat", failing_collect)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(chat_api.chat(_payload()))

    assert exc_info.value.status_code == 503
    assert workload._active_chats == 0


def test_chat_stream_releases_priority_on_disconnect(monkeypatch):
    async def fake_run_chat(state):
        assert workload._active_chats == 1
        yield {"event": "status", "data": {"stage": "generating"}}
        await asyncio.Event().wait()

    monkeypatch.setattr(chat_api, "run_chat", fake_run_chat)

    async def scenario():
        response = await chat_api.chat_stream(_payload())
        iterator = response.body_iterator
        event = await anext(iterator)
        assert "status" in event
        assert workload._active_chats == 1
        await iterator.aclose()

    asyncio.run(scenario())

    assert workload._active_chats == 0


def test_ingest_slot_blocks_while_chat_active(monkeypatch):
    monkeypatch.setenv("VLM_INGEST_QUEUE_TIMEOUT", "0.05")
    workload.chat_started()
    try:
        with pytest.raises(TimeoutError):
            with workload.ingest_slot():
                pass
    finally:
        workload.chat_finished()


def test_ingest_slot_resumes_after_chat_finishes(monkeypatch):
    monkeypatch.setenv("VLM_INGEST_QUEUE_TIMEOUT", "1")
    workload.chat_started()
    entered = threading.Event()
    errors: list[BaseException] = []

    def run_ingest():
        try:
            with workload.ingest_slot():
                entered.set()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    thread = threading.Thread(target=run_ingest)
    thread.start()
    try:
        assert not entered.wait(0.05)
    finally:
        workload.chat_finished()

    assert entered.wait(1)
    thread.join(timeout=1)
    assert not thread.is_alive()
    assert errors == []
