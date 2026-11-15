"""Tests cho pipeline tuyến tính: greeting, LMS, citation gate, no-docs."""

import asyncio

from app.workflow.generation import _system_prompt
from app.workflow.pipeline import (
    _allows_no_citation,
    _run_chat,
    _source_list,
    _stream_with_citation_gate,
    greeting_reply,
)
from app.workflow.query import QueryPrep
from app.workflow.state import ChatState


def _state(**overrides) -> ChatState:
    values = {
        "question": "Câu hỏi",
        "course_id": "course-1",
        "thread_id": "thread-1",
    }
    values.update(overrides)
    return ChatState(**values)


def _doc(doc_id: str = "doc-1") -> dict:
    return {
        "id": doc_id,
        "course_id": "course-1",
        "lesson_id": "lesson-1",
        "slide_id": "slide-1",
        "asset_id": "asset-1",
        "pdf_object_key": "pdf/key.pdf",
        "pdf_storage_backend": "local",
        "pdf_mime_type": "application/pdf",
        "source_page": 2,
        "content": "Nội dung",
        "slide_title": "Slide",
        "module_title": "Chương 1",
        "lesson_title": "Bài 1",
        "slide_index": 1,
    }


async def _collect(agen):
    return [event async for event in agen]


def test_greeting_reply_matches_whole_utterance():
    assert greeting_reply("Xin chào!") is not None
    assert greeting_reply("Cảm ơn bạn") is not None
    assert greeting_reply("Chào bạn, giải thích khái niệm X") is None


def test_source_list_and_no_citation_detection():
    citations = [{"title": "Chương 1 - Bài 1", "slide_index": 2}]
    text = _source_list(citations)

    assert "Nguồn tham khảo:" in text
    assert "[1] Chương 1 - Bài 1 (slide 2)" in text
    assert _allows_no_citation("Mình không tìm thấy nội dung này trong tài liệu.")
    assert _allows_no_citation("Ngoài tài liệu môn học: ví dụ này...")
    assert not _allows_no_citation("Đây là câu trả lời có nội dung.")


def test_citation_gate_retries_then_accepts(monkeypatch):
    calls = {"count": 0}

    async def fake_stream(state, strict=False):
        calls["count"] += 1
        if strict:
            yield "Câu trả lời đã sửa [1]."
        else:
            yield "Câu trả lời chưa có citation."

    monkeypatch.setattr("app.workflow.pipeline.stream_answer", fake_stream)
    monkeypatch.setattr("app.workflow.pipeline.citation_gate_tokens", lambda: 5)
    monkeypatch.setattr("app.workflow.pipeline.citation_retry_max", lambda: 1)

    state = _state()
    state.citations = [{"title": "Slide 1", "slide_index": 1}]
    events = asyncio.run(_collect(_stream_with_citation_gate(state)))
    text = "".join(event["data"]["text"] for event in events if event["event"] == "token")

    assert calls["count"] == 2
    assert "[1]" in text
    assert state.verified is True
    assert state.finish_reason == "stop"


def test_citation_gate_falls_back_to_source_list(monkeypatch):
    async def fake_stream(state, strict=False):
        yield "Câu trả lời không có citation."

    monkeypatch.setattr("app.workflow.pipeline.stream_answer", fake_stream)
    monkeypatch.setattr("app.workflow.pipeline.citation_gate_tokens", lambda: 5)
    monkeypatch.setattr("app.workflow.pipeline.citation_retry_max", lambda: 1)

    state = _state()
    state.citations = [{"title": "Slide 1", "slide_index": 1}]
    events = asyncio.run(_collect(_stream_with_citation_gate(state)))
    text = "".join(event["data"]["text"] for event in events if event["event"] == "token")

    assert "Nguồn tham khảo:" in text
    assert state.verified is False
    assert state.finish_reason == "citation_failed"


def test_citation_gate_allows_not_found_answer(monkeypatch):
    async def fake_stream(state, strict=False):
        yield "Mình không tìm thấy nội dung này trong tài liệu môn học."

    monkeypatch.setattr("app.workflow.pipeline.stream_answer", fake_stream)
    monkeypatch.setattr("app.workflow.pipeline.citation_gate_tokens", lambda: 5)
    monkeypatch.setattr("app.workflow.pipeline.citation_retry_max", lambda: 1)

    state = _state()
    state.citations = [{"title": "Slide 1", "slide_index": 1}]
    events = asyncio.run(_collect(_stream_with_citation_gate(state)))
    text = "".join(event["data"]["text"] for event in events if event["event"] == "token")

    assert "không tìm thấy" in text
    assert state.verified is False
    assert state.finish_reason == "insufficient_evidence"


def test_system_prompt_adds_hint_and_review_suffix():
    hint = _state(assignment_context="Bài tập", support_mode="hint")
    review = _state(assignment_context="Bài tập", support_mode="review")

    assert "BÀI TẬP CHƯA NỘP" in _system_prompt(hint)
    assert "BÀI TẬP ĐÃ NỘP" in _system_prompt(review)


def test_run_chat_greeting_fast_path(monkeypatch):
    async def noop(state):
        return None

    monkeypatch.setattr("app.workflow.lms.check_access", noop)

    state = _state(question="Xin chào")
    events = asyncio.run(_collect(_run_chat(state)))
    tokens = "".join(
        event["data"]["text"] for event in events if event["event"] == "token"
    )
    done = next(event for event in events if event["event"] == "done")

    assert "Chào bạn" in tokens
    assert done["data"]["intent"] == "general"


def test_run_chat_pure_lms_skips_query_prep(monkeypatch):
    async def noop(state):
        return None

    async def fake_query(state, operation, target=""):
        return {"assignments": []}

    async def fail_prepare(state):
        raise AssertionError("prepare_query không được gọi cho pure LMS")

    monkeypatch.setattr("app.workflow.lms.check_access", noop)
    monkeypatch.setattr("app.workflow.lms.detect_operation", lambda question: "assignments")
    monkeypatch.setattr("app.workflow.lms.is_pure_lms", lambda question: True)
    monkeypatch.setattr("app.workflow.lms.query", fake_query)
    monkeypatch.setattr("app.workflow.lms.render", lambda data, operation: "LMS answer")
    monkeypatch.setattr("app.workflow.pipeline.prepare_query", fail_prepare)

    state = _state(question="Hạn nộp bài tập 1")
    events = asyncio.run(_collect(_run_chat(state)))
    tokens = "".join(
        event["data"]["text"] for event in events if event["event"] == "token"
    )
    done = next(event for event in events if event["event"] == "done")

    assert tokens == "LMS answer"
    assert done["data"]["intent"] == "lms"


def test_run_chat_no_docs_returns_insufficient_evidence(monkeypatch):
    async def noop(state):
        return None

    class FakeRetriever:
        async def asearch(self, query, hyde, course_id):
            return []

    async def fake_prepare(state):
        return QueryPrep(query="q")

    monkeypatch.setattr("app.workflow.lms.check_access", noop)
    monkeypatch.setattr("app.workflow.lms.detect_operation", lambda question: None)
    monkeypatch.setattr("app.workflow.pipeline.prepare_query", fake_prepare)
    monkeypatch.setattr("app.workflow.pipeline.get_retriever", lambda: FakeRetriever())

    state = _state(question="Khái niệm X là gì?")
    events = asyncio.run(_collect(_run_chat(state)))
    tokens = "".join(
        event["data"]["text"] for event in events if event["event"] == "token"
    )
    done = next(event for event in events if event["event"] == "done")

    assert "chưa tìm thấy" in tokens
    assert done["data"]["verified"] is False
    assert done["data"]["finish_reason"] == "insufficient_evidence"


def test_run_chat_knowledge_path_emits_citations_and_done(monkeypatch):
    async def noop(state):
        return None

    class FakeRetriever:
        async def asearch(self, query, hyde, course_id):
            return [_doc()]

    async def fake_prepare(state):
        return QueryPrep(query="q")

    async def fake_stream(state, strict=False):
        yield "Câu trả lời [1]."

    monkeypatch.setattr("app.workflow.lms.check_access", noop)
    monkeypatch.setattr("app.workflow.lms.detect_operation", lambda question: None)
    monkeypatch.setattr("app.workflow.pipeline.prepare_query", fake_prepare)
    monkeypatch.setattr("app.workflow.pipeline.get_retriever", lambda: FakeRetriever())
    monkeypatch.setattr("app.workflow.pipeline.stream_answer", fake_stream)

    state = _state(question="Khái niệm X là gì?")
    events = asyncio.run(_collect(_run_chat(state)))
    citations = next(event for event in events if event["event"] == "citations")
    done = next(event for event in events if event["event"] == "done")

    assert len(citations["data"]["citations"]) == 1
    assert done["data"]["verified"] is True
    assert done["data"]["intent"] == "course_qa"
