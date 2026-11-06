import asyncio

import pytest

from app.workflow import blocks, graph
from app.workflow.router import RoutePlan


def state(**kw):
    return {"question": "Khóa chính?", "course_id": "course", "course_version_id": "course-version", "thread_id": "thread", "history": [], **kw}


@pytest.fixture
def fake(monkeypatch):
    async def access(s): pass
    async def plan(s): return RoutePlan(routes=["knowledge"]).model_dump()
    async def lookup(s, op, target=""):
        return {"course": {"title": "Course", "description": "", "url": "/student/courses/course"}}
    class Retriever:
        async def asearch(self, q, c, cv):
            return [{"id": "slide", "course_id": c, "course_version_id": cv, "content": "Source", "module_title": "M", "lesson_title": "L", "course_title": "C"}]
    async def generate(s):
        yield "First [1]"
        yield "Second [1]"
    async def verify(s, text): return {"ok": True}
    monkeypatch.setattr(graph.lms, "check_access", access)
    monkeypatch.setattr(graph.lms, "query", lookup)
    monkeypatch.setattr(graph, "route_plan", plan)
    monkeypatch.setattr(graph, "get_retriever", Retriever)
    monkeypatch.setattr(blocks, "answer_blocks", generate)
    monkeypatch.setattr(blocks, "verify_answer_async", verify)


def collect(s):
    async def run(): return [e async for e in graph.stream_graph(s)]
    return asyncio.run(run())


def test_graph_knowledge_only_custom_approved_events(fake):
    events = collect(state())
    assert [e['data']['text'] for e in events if e['event'] == 'token'] == ['First [1]', '\n\nSecond [1]']
    assert events[-1]['data']['routes'] == ['knowledge']
    assert events[-1]['event'] == 'done'
    assert next(i for i,e in enumerate(events) if e['event']=='citations') < next(i for i,e in enumerate(events) if e['event']=='token')


def test_mixed_lms_first_without_rewrite(fake, monkeypatch):
    async def plan(s): return RoutePlan(routes=['lms','knowledge'], operation='course').model_dump()
    monkeypatch.setattr(graph, 'route_plan', plan)
    events = collect(state())
    assert [e['data']['route'] for e in events if e['event']=='token'] == ['lms','knowledge','knowledge']
    assert events[-1]['data']['routes'] == ['lms','knowledge']


def test_general_no_retrieval(fake, monkeypatch):
    async def plan(s): return RoutePlan(routes=['general']).model_dump()
    monkeypatch.setattr(graph, 'route_plan', plan)
    monkeypatch.setattr(graph, 'get_retriever', lambda: pytest.fail('retrieval called'))
    events = collect(state(question='Xin chào'))
    assert len([e for e in events if e['event']=='token']) == 1


def test_foreign_course_rejected(fake, monkeypatch):
    class Bad:
        async def asearch(self,q,c,cv): return [{'course_id':'other','course_version_id':cv}]
    monkeypatch.setattr(graph, 'get_retriever', Bad)
    with pytest.raises(ValueError, match='foreign course'):
        collect(state())


def test_cancel_generation_on_browser_abort(fake, monkeypatch):
    closed = []
    async def generate(s):
        try:
            yield 'First [1]'
            await asyncio.Event().wait()
        finally:
            closed.append(True)
    monkeypatch.setattr(blocks, 'answer_blocks', generate)
    async def run():
        stream = graph.stream_graph(state())
        async for event in stream:
            if event['event']=='token': break
        await stream.aclose()
    asyncio.run(run())
    assert closed


def test_dependent_mixed_lookup_precedes_retrieval(fake, monkeypatch):
    order=[]
    async def plan(s): return RoutePlan(routes=['lms','knowledge'], operation='assignment', depends_on_lms=True).model_dump()
    async def lookup(s,op,target=''):
        order.append('lms')
        return {'assignments':[]}
    class R:
        async def asearch(self,q,c,cv):
            assert order == ['lms']
            order.append('retrieval')
            return []
    monkeypatch.setattr(graph,'route_plan',plan)
    monkeypatch.setattr(graph.lms,'query',lookup)
    monkeypatch.setattr(graph,'get_retriever',R)
    collect(state())
    assert order == ['lms','retrieval']


def test_revoked_access_never_emits_another_block(fake, monkeypatch):
    seen=[]
    async def access(s):
        seen.append(1)
        if len(seen)==3: raise graph.lms.AccessRevoked('revoked')
    monkeypatch.setattr(graph.lms,'check_access',access)
    async def run():
        emitted=[]
        with pytest.raises(graph.lms.AccessRevoked):
            async for event in graph.stream_graph(state()):emitted.append(event)
        return emitted
    events=asyncio.run(run())
    assert len([e for e in events if e['event']=='token'])==1
    assert not any(e['event']=='done' for e in events)


def test_internal_session_course_mismatch_is_rejected(monkeypatch):
    import httpx

    from app.workflow import lms
    class Client:
        async def post(self,*args,**kwargs):
            return httpx.Response(200,request=httpx.Request('POST','http://backend/internal/chat/lms-query'),json={'course_id':'other','allowed':True})
    monkeypatch.setattr(lms,'backend_client',Client)
    with pytest.raises(lms.AccessRevoked,match='khóa học'):
        asyncio.run(lms.check_access(state()))
