"""Query pipeline: retrieval thật, mock LLM, citation gate, SSE, LMS."""

from __future__ import annotations

import json
import uuid

import httpx
import pytest
import respx

from tests.support import db

pytestmark = pytest.mark.fast


def _payload(course_id: str, message: str = "alpha là gì?", **extra) -> dict:
    data = {
        "message": message,
        "course_id": course_id,
        "thread_id": str(uuid.uuid4()),
        "context_key": "ctx",
        "history": [],
    }
    data.update(extra)
    return data


def _events(text: str) -> list[tuple[str, dict]]:
    events = []
    event = None
    for line in text.splitlines():
        if line.startswith("event: "):
            event = line[7:]
        elif line.startswith("data: ") and event:
            events.append((event, json.loads(line[6:])))
    return events


def _lms_ok(course_id: str):
    return httpx.Response(
        200,
        json={"course_id": course_id, "allowed": True, "server_now": "2026-01-01T00:00:00Z"},
    )


class FakeRetriever:
    def __init__(self, docs=None):
        self.docs = docs or []
        self.calls = 0

    async def asearch(self, query, hyde, course_id):
        self.calls += 1
        return list(self.docs)


def _doc(course_id: str, slide_id: str, lesson_id: str, text: str) -> dict:
    return {
        "id": slide_id,
        "course_id": course_id,
        "lesson_id": lesson_id,
        "asset_id": str(uuid.uuid4()),
        "pdf_object_key": "test/slides.pdf",
        "pdf_storage_backend": "local",
        "pdf_mime_type": "application/pdf",
        "source_page": 1,
        "content": text,
        "slide_title": "Slide 1",
        "module_title": "Chương 1",
        "lesson_title": "Bài 1",
        "slide_index": 1,
    }


@respx.mock
async def test_greeting_skips_retrieval_and_llm(client, fake_providers):
    seeded = db.seed_course()
    retriever = FakeRetriever()
    import app.workflow.pipeline as pipeline

    original = pipeline.get_retriever
    pipeline.get_retriever = lambda: retriever
    respx.post("http://backend:8001/internal/chat/lms-query").mock(
        return_value=_lms_ok(seeded["course_id"])
    )
    try:
        response = await client.post(
            "/chat", json=_payload(seeded["course_id"], "Xin chào")
        )
    finally:
        pipeline.get_retriever = original
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["intent"] == "general"
    assert body["routes"] == ["general"]
    assert retriever.calls == 0
    assert fake_providers.llm.stream_calls == 0


@respx.mock
async def test_no_documents_returns_fallback(client, fake_providers):
    seeded = db.seed_course()
    import app.workflow.pipeline as pipeline

    original = pipeline.get_retriever
    pipeline.get_retriever = lambda: FakeRetriever([])
    respx.post("http://backend:8001/internal/chat/lms-query").mock(
        return_value=_lms_ok(seeded["course_id"])
    )
    try:
        response = await client.post(
            "/chat", json=_payload(seeded["course_id"], "không có gì")
        )
    finally:
        pipeline.get_retriever = original
    assert response.status_code == 200
    body = response.json()
    assert "chưa tìm thấy nội dung phù hợp" in body["answer"]
    assert body["citations"] == []
    assert body["verified"] is False
    assert body["finish_reason"] == "insufficient_evidence"


@respx.mock
async def test_retrieval_filters_course_and_returns_citation(client, fake_providers):
    first = db.seed_course(slide_transcripts=["alpha A", "beta A"])
    second = db.seed_course(slide_transcripts=["alpha B"])
    respx.post("http://backend:8001/internal/chat/lms-query").mock(
        return_value=_lms_ok(first["course_id"])
    )
    response = await client.post(
        "/chat", json=_payload(first["course_id"], "alpha")
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answer"] == "Câu trả lời [1]."
    assert body["citations"], body
    returned = {citation["slide_id"] for citation in body["citations"]}
    assert returned <= set(first["slide_ids"])
    assert not (returned & set(second["slide_ids"]))
    assert body["verified"] is True


@respx.mock
async def test_stream_event_order_and_done(client, fake_providers):
    seeded = db.seed_course()
    doc = _doc(seeded["course_id"], "slide-1", seeded["lesson_id"], "alpha")
    import app.workflow.pipeline as pipeline

    original = pipeline.get_retriever
    pipeline.get_retriever = lambda: FakeRetriever([doc])
    respx.post("http://backend:8001/internal/chat/lms-query").mock(
        return_value=_lms_ok(seeded["course_id"])
    )
    try:
        response = await client.post(
            "/chat/stream", json=_payload(seeded["course_id"], "alpha là gì?")
        )
    finally:
        pipeline.get_retriever = original
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _events(response.text)
    names = [name for name, _ in events]
    assert names[0] == "status"
    assert "citations" in names
    assert "token" in names
    assert names[-1] == "done"
    done = events[-1][1]
    assert done["intent"] == "course_qa"
    assert done["citation_count"] == 1
    assert done["verified"] is True
    assert done["finish_reason"] == "stop"


@respx.mock
async def test_citation_gate_retries_then_accepts(client, fake_providers, monkeypatch):
    seeded = db.seed_course()
    doc = _doc(seeded["course_id"], "slide-1", seeded["lesson_id"], "alpha")
    import app.workflow.pipeline as pipeline

    original = pipeline.get_retriever
    pipeline.get_retriever = lambda: FakeRetriever([doc])
    monkeypatch.setattr(pipeline, "citation_gate_tokens", lambda: 5)
    monkeypatch.setattr(pipeline, "citation_retry_max", lambda: 1)
    fake_providers.llm.chunks_by_call = {
        1: ["Câu trả lời không citation."],
        2: ["Câu trả lời đã sửa [1]."],
    }
    respx.post("http://backend:8001/internal/chat/lms-query").mock(
        return_value=_lms_ok(seeded["course_id"])
    )
    try:
        response = await client.post(
            "/chat/stream", json=_payload(seeded["course_id"], "alpha")
        )
    finally:
        pipeline.get_retriever = original
    events = _events(response.text)
    tokens = "".join(
        data["text"] for name, data in events if name == "token"
    )
    assert "[1]" in tokens
    done = events[-1][1]
    assert done["verified"] is True
    assert fake_providers.llm.stream_calls == 2


@respx.mock
async def test_citation_gate_falls_back_to_source_list(
    client, fake_providers, monkeypatch
):
    seeded = db.seed_course()
    doc = _doc(seeded["course_id"], "slide-1", seeded["lesson_id"], "alpha")
    import app.workflow.pipeline as pipeline

    original = pipeline.get_retriever
    pipeline.get_retriever = lambda: FakeRetriever([doc])
    monkeypatch.setattr(pipeline, "citation_gate_tokens", lambda: 5)
    monkeypatch.setattr(pipeline, "citation_retry_max", lambda: 1)
    fake_providers.llm.chunks = ["Câu trả lời không citation."]
    respx.post("http://backend:8001/internal/chat/lms-query").mock(
        return_value=_lms_ok(seeded["course_id"])
    )
    try:
        response = await client.post(
            "/chat/stream", json=_payload(seeded["course_id"], "alpha")
        )
    finally:
        pipeline.get_retriever = original
    events = _events(response.text)
    text = "".join(data["text"] for name, data in events if name == "token")
    assert "Nguồn tham khảo:" in text
    done = events[-1][1]
    assert done["verified"] is False
    assert done["finish_reason"] == "citation_failed"


@respx.mock
async def test_non_stream_strips_invalid_citation(client, fake_providers):
    seeded = db.seed_course()
    doc = _doc(seeded["course_id"], "slide-1", seeded["lesson_id"], "alpha")
    import app.workflow.pipeline as pipeline

    original = pipeline.get_retriever
    pipeline.get_retriever = lambda: FakeRetriever([doc])
    fake_providers.llm.chunks = ["Đáp án [99] và [1]."]
    respx.post("http://backend:8001/internal/chat/lms-query").mock(
        return_value=_lms_ok(seeded["course_id"])
    )
    try:
        response = await client.post(
            "/chat", json=_payload(seeded["course_id"], "alpha")
        )
    finally:
        pipeline.get_retriever = original
    assert response.status_code == 200
    assert "[99]" not in response.json()["answer"]
    assert "[1]" in response.json()["answer"]


@respx.mock
async def test_pure_lms_renders_without_llm(client, fake_providers):
    seeded = db.seed_course()
    respx.post("http://backend:8001/internal/chat/lms-query").mock(
        return_value=httpx.Response(
            200,
            json={
                "course_id": seeded["course_id"],
                "allowed": True,
                "server_now": "2026-01-01T00:00:00Z",
                "assignments": [
                    {
                        "id": seeded["lesson_id"],
                        "lesson_id": seeded["lesson_id"],
                        "title": "Bài tập 1",
                        "status": "chưa làm",
                        "due_at": None,
                        "attempt_deadline": None,
                        "remaining_seconds": None,
                        "duration_minutes": 30,
                        "url": "/student/courses/x?lesson=y",
                        "instructions": "",
                    }
                ],
            },
        )
    )
    response = await client.post(
        "/chat", json=_payload(seeded["course_id"], "deadline bài tập")
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["intent"] == "lms"
    assert body["routes"] == ["lms"]
    assert "Bài tập 1" in body["answer"]
    assert fake_providers.llm.stream_calls == 0


@respx.mock
async def test_lms_revoked_returns_error_event(client, fake_providers):
    seeded = db.seed_course()
    respx.post("http://backend:8001/internal/chat/lms-query").mock(
        return_value=httpx.Response(403, json={"detail": "revoked"})
    )
    response = await client.post(
        "/chat/stream", json=_payload(seeded["course_id"], "deadline bài tập")
    )
    assert response.status_code == 200
    events = _events(response.text)
    assert events[-1][0] == "error"
    assert "không thể hoàn tất" in events[-1][1]["message"]


async def test_request_validation(client, fake_providers):
    seeded = db.seed_course()
    too_long_history = [
        {"role": "student", "content": "x"} for _ in range(31)
    ]
    response = await client.post(
        "/chat",
        json=_payload(seeded["course_id"], "hỏi", history=too_long_history),
    )
    assert response.status_code == 422
