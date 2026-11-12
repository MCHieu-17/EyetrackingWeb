"""Tests cho query rewrite + adaptive HyDE."""

import asyncio

from app.workflow.query import (
    QueryPrep,
    RewriteOnly,
    _needs_hyde,
    _needs_rewrite,
    prepare_query,
)
from app.workflow.state import ChatState


def _state(question: str, history: list[dict] | None = None) -> ChatState:
    return ChatState(
        question=question,
        course_id="course-1",
        course_version_id="version-1",
        thread_id="thread-1",
        history=history or [],
    )


class _FakeLLM:
    def __init__(self, result: QueryPrep | None = None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.calls = 0

    async def structured(self, purpose, prompt, schema):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result or schema(query="rewritten", hypothetical_answer="hyde")


def test_needs_rewrite_only_with_history_and_reference():
    assert _needs_rewrite(_state("Giải thích khái niệm này")) is False
    assert (
        _needs_rewrite(
            _state(
                "Giải thích thêm",
                history=[{"role": "student", "content": "Khái niệm A là gì?"}],
            )
        )
        is True
    )


def test_needs_hyde_for_short_question(monkeypatch):
    monkeypatch.setattr("app.workflow.query.hyde_enabled", lambda: True)
    monkeypatch.setattr("app.workflow.query.hyde_min_query_words", lambda: 8)

    assert _needs_hyde(_state("Tại sao?")) is True
    assert _needs_hyde(_state("Giải thích thêm")) is True
    # Câu ngắn nhưng có chủ thể cụ thể không cần HyDE.
    assert _needs_hyde(_state("AWS Glue là gì?")) is False
    assert _needs_hyde(_state("Giải thích AWS Glue")) is False
    # Follow-up đã có rewrite xử lý, không cần HyDE.
    assert (
        _needs_hyde(
            _state(
                "Nó khác gì Athena?",
                history=[{"role": "student", "content": "AWS Glue là gì?"}],
            )
        )
        is False
    )
    assert (
        _needs_hyde(
            _state(
                "Giải thích chi tiết sự khác biệt giữa primary key và foreign key "
                "trong cơ sở dữ liệu quan hệ"
            )
        )
        is False
    )


def test_prepare_query_skips_call_for_clear_question(monkeypatch):
    monkeypatch.setattr("app.workflow.query.hyde_enabled", lambda: True)
    monkeypatch.setattr("app.workflow.query.hyde_min_query_words", lambda: 8)
    monkeypatch.setattr("app.workflow.query.query_rewrite_enabled", lambda: True)
    fake = _FakeLLM()
    monkeypatch.setattr("app.workflow.query.get_llm_client", lambda: fake)

    state = _state(
        "Giải thích chi tiết sự khác biệt giữa primary key và foreign key "
        "trong cơ sở dữ liệu quan hệ"
    )
    prep = asyncio.run(prepare_query(state))

    assert prep.query == state.question
    assert prep.hypothetical_answer == ""
    assert fake.calls == 0


def test_prepare_query_uses_hyde_for_short_question(monkeypatch):
    monkeypatch.setattr("app.workflow.query.hyde_enabled", lambda: True)
    monkeypatch.setattr("app.workflow.query.hyde_min_query_words", lambda: 8)
    monkeypatch.setattr("app.workflow.query.query_rewrite_enabled", lambda: True)
    fake = _FakeLLM(
        result=QueryPrep(query="truy vấn đã viết lại", hypothetical_answer="hyde text")
    )
    monkeypatch.setattr("app.workflow.query.get_llm_client", lambda: fake)

    prep = asyncio.run(prepare_query(_state("Tại sao?")))

    assert prep.query == "truy vấn đã viết lại"
    assert prep.hypothetical_answer == "hyde text"
    assert fake.calls == 1


def test_prepare_query_rewrite_only_uses_rewrite_schema(monkeypatch):
    monkeypatch.setattr("app.workflow.query.hyde_enabled", lambda: True)
    monkeypatch.setattr("app.workflow.query.hyde_min_query_words", lambda: 8)
    monkeypatch.setattr("app.workflow.query.query_rewrite_enabled", lambda: True)
    fake = _FakeLLM(result=RewriteOnly(query="Glue khác gì Athena?"))
    monkeypatch.setattr("app.workflow.query.get_llm_client", lambda: fake)

    state = _state(
        "Nó khác gì Athena?",
        history=[{"role": "student", "content": "AWS Glue là gì?"}],
    )
    prep = asyncio.run(prepare_query(state))

    assert prep.query == "Glue khác gì Athena?"
    assert prep.hypothetical_answer == ""
    assert fake.calls == 1


def test_prepare_query_falls_back_on_error(monkeypatch):
    monkeypatch.setattr("app.workflow.query.hyde_enabled", lambda: True)
    monkeypatch.setattr("app.workflow.query.hyde_min_query_words", lambda: 8)
    monkeypatch.setattr("app.workflow.query.query_rewrite_enabled", lambda: True)
    fake = _FakeLLM(error=RuntimeError("provider down"))
    monkeypatch.setattr("app.workflow.query.get_llm_client", lambda: fake)

    state = _state("Tại sao?")
    prep = asyncio.run(prepare_query(state))

    assert prep.query == state.question
    assert prep.hypothetical_answer == ""
