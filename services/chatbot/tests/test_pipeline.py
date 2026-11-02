import asyncio

from app.workflow import pipeline
from app.workflow.guardrails import safe_response


def _doc():
    return {
        "id": "slide-1",
        "lesson_id": "lesson-1",
        "content": "Khóa chính xác định duy nhất mỗi hàng.",
        "course_title": "Cơ sở dữ liệu",
        "module_title": "Chương 1",
        "lesson_title": "Bài 1",
        "image_url": "/media/slide.jpg",
        "slide_index": 1,
        "score": 0.9,
    }


def _state():
    return {
        "question": "Khóa chính là gì?",
        "course_id": "course-1",
        "thread_id": "thread-1",
        "history": [],
        "assignment_context": "",
        "support_mode": "hint",
        "attempts": 0,
    }


class _FakeRetriever:
    def search(self, _query, _course_id):
        return [_doc()]


def test_collect_chat_success(monkeypatch):
    monkeypatch.setattr(pipeline, "route", lambda _state: "course_qa")
    monkeypatch.setattr(pipeline, "get_retriever", lambda: _FakeRetriever())
    monkeypatch.setattr(pipeline, "answer", lambda _state: "Khóa chính xác định duy nhất mỗi hàng [1].")
    monkeypatch.setattr(
        pipeline,
        "verify_answer",
        lambda _state, _draft: {"ok": True, "feedback": "", "claims": [], "no_solution_ok": True},
    )
    monkeypatch.setattr(pipeline, "citation_max_attempts", lambda: 2)

    answer, citations, intent, verified = asyncio.run(pipeline.collect_chat(_state()))

    assert answer == "Khóa chính xác định duy nhất mỗi hàng [1]."
    assert citations[0]["document_id"] == "slide-1"
    assert intent == "course_qa"
    assert verified is True


def test_collect_chat_verification_failure_returns_safe_response(monkeypatch):
    monkeypatch.setattr(pipeline, "route", lambda _state: "course_qa")
    monkeypatch.setattr(pipeline, "get_retriever", lambda: _FakeRetriever())
    monkeypatch.setattr(pipeline, "answer", lambda _state: "Draft sai [1].")
    monkeypatch.setattr(
        pipeline,
        "verify_answer",
        lambda _state, _draft: {
            "ok": False,
            "feedback": "citation sai",
            "claims": [],
            "no_solution_ok": False,
        },
    )
    monkeypatch.setattr(pipeline, "citation_max_attempts", lambda: 2)

    answer, _citations, intent, verified = asyncio.run(pipeline.collect_chat(_state()))

    assert answer == safe_response("course_qa")
    assert intent == "course_qa"
    assert verified is False


def test_collect_chat_study_skills_skips_retrieval(monkeypatch):
    monkeypatch.setattr(pipeline, "route", lambda _state: "study_skills")
    monkeypatch.setattr(
        pipeline,
        "get_retriever",
        lambda: (_ for _ in ()).throw(AssertionError("không được retrieve")),
    )
    monkeypatch.setattr(pipeline, "answer", lambda _state: "Hãy học theo Pomodoro.")
    monkeypatch.setattr(
        pipeline,
        "verify_answer",
        lambda _state, _draft: (_ for _ in ()).throw(AssertionError("không được verify")),
    )

    answer, citations, intent, verified = asyncio.run(pipeline.collect_chat(_state()))

    assert answer == "Hãy học theo Pomodoro."
    assert citations == []
    assert intent == "study_skills"
    assert verified is True


def test_run_chat_emits_status_and_done(monkeypatch):
    monkeypatch.setattr(pipeline, "route", lambda _state: "study_skills")
    monkeypatch.setattr(pipeline, "answer", lambda _state: "Một hai ba.")

    async def _collect():
        events = []
        async for event in pipeline.run_chat(_state()):
            events.append(event)
        return events

    events = asyncio.run(_collect())
    names = [event["event"] for event in events]
    assert "status" in names
    assert "token" in names
    assert names[-1] == "done"
