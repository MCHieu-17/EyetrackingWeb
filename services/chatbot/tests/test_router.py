from app.workflow import router as router_mod
from app.workflow.router import RouterOutput, route


class _FakeChain:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def invoke(self, _payload):
        if self.error is not None:
            raise self.error
        return self.result


def _state(**overrides):
    data = {
        "question": "Khóa chính là gì?",
        "course_id": "course-1",
        "thread_id": "thread-1",
        "history": [],
        "assignment_context": "",
        "support_mode": "hint",
    }
    data.update(overrides)
    return data


def test_review_shortcut():
    state = _state(support_mode="review", assignment_context="Bài tập đã nộp")
    assert route(state) == "exercise_review"


def test_hint_shortcut():
    state = _state(support_mode="hint", assignment_context="Bài tập đang làm")
    assert route(state) == "exercise_hints"


def test_llm_classification(monkeypatch):
    monkeypatch.setattr(
        router_mod,
        "_router_chain",
        lambda: _FakeChain(RouterOutput(intent="study_skills")),
    )
    assert route(_state()) == "study_skills"


def test_llm_error_defaults_to_course_qa(monkeypatch):
    monkeypatch.setattr(
        router_mod,
        "_router_chain",
        lambda: _FakeChain(error=RuntimeError("boom")),
    )
    assert route(_state()) == "course_qa"
