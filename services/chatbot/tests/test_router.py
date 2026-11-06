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


def test_review_shortcut(monkeypatch):
    monkeypatch.setattr(router_mod, "_router_chain", lambda: _FakeChain(RouterOutput(intent="course_qa")))
    state = _state(support_mode="review", assignment_context="Bài tập đã nộp")
    assert route(state) == "exercise_review"


def test_hint_shortcut(monkeypatch):
    monkeypatch.setattr(router_mod, "_router_chain", lambda: _FakeChain(RouterOutput(intent="course_qa")))
    state = _state(support_mode="hint", assignment_context="Bài tập đang làm")
    assert route(state) == "exercise_hints"


def test_llm_classification(monkeypatch):
    monkeypatch.setattr(
        router_mod,
        "_router_chain",
        lambda: _FakeChain(RouterOutput(intent="study_skills")),
    )
    assert route(_state()) == "study_skills"


def test_llm_error_requests_clarification(monkeypatch):
    monkeypatch.setattr(
        router_mod,
        "_router_chain",
        lambda: _FakeChain(error=RuntimeError("boom")),
    )
    assert route(_state()) == "clarify"


def test_greeting_during_exercise(monkeypatch):
    monkeypatch.setattr(router_mod, "_router_chain", lambda: (_ for _ in ()).throw(AssertionError("AI called")))
    assert route(_state(question="Xin chào!", assignment_context="Quiz")) == "general"


def test_mixed_greeting(monkeypatch):
    monkeypatch.setattr(router_mod, "_router_chain", lambda: _FakeChain(RouterOutput(intent="course_qa")))
    assert route(_state(question="Xin chào, giải thích khóa chính")) == "course_qa"


def test_new_router_fast_paths_never_call_river(monkeypatch):
    import asyncio

    from app.workflow import river
    monkeypatch.setattr(river,'get_river',lambda: (_ for _ in ()).throw(AssertionError('River called')))
    for question,expected in [('Xin chào','general'),('hạn nộp bài tập','lms'),('điểm của tôi','lms')]:
        plan=asyncio.run(router_mod.route_plan(_state(question=question,assignment_context='quiz')))
        assert plan['routes']==[expected]


def test_new_router_provider_error_is_clarification(monkeypatch):
    import asyncio

    from app.workflow import river
    class Failed:
        async def structured(self,*args): raise RuntimeError('provider down')
    monkeypatch.setattr(river,'get_river',Failed)
    plan=asyncio.run(router_mod.route_plan(_state()))
    assert plan['routes']==['general'] and plan['clarification']
