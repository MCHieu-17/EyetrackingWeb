import asyncio
import functools

def async_test(fn):
    @functools.wraps(fn)
    def run(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))
    return run
from app.workflow import blocks

@async_test
async def test_first_block_before_generation_finishes(monkeypatch):
    release = asyncio.Event()
    async def generate(state):
        yield 'First [1]'
        await release.wait()
        yield 'Second [1]'
    monkeypatch.setattr(blocks, 'answer_blocks', generate)
    async def verify(state, text):
        return {'ok': True}
    monkeypatch.setattr(blocks, 'verify_answer_async', verify)
    stream = blocks.verified_blocks({'intent': 'course_qa', 'citations': [{}]})
    assert (await asyncio.wait_for(anext(stream), 1))['data']['text'] == 'First [1]'
    release.set()
    assert (await anext(stream))['data']['text'] == '\n\nSecond [1]'
    await stream.aclose()

@async_test
async def test_invalid_citation_and_one_repair(monkeypatch):
    calls = []
    async def generate(state):
        calls.append(1)
        yield 'Untrusted [99]'
    monkeypatch.setattr(blocks, 'answer_blocks', generate)
    events = [e async for e in blocks.verified_blocks({'intent': 'course_qa', 'citations': []})]
    assert len(calls) == 2
    assert all('Untrusted' not in e['data']['text'] for e in events)

@async_test
async def test_cumulative_verification(monkeypatch):
    seen = []
    async def generate(state):
        yield 'One [1]'
        yield 'Two [1]'
    async def verify(state, text):
        seen.append(text)
        return {'ok': True}
    monkeypatch.setattr(blocks, 'answer_blocks', generate)
    monkeypatch.setattr(blocks, 'verify_answer_async', verify)
    _ = [e async for e in blocks.verified_blocks({'intent': 'exercise_hints', 'citations': [{}]})]
    assert seen == ['One [1]', 'One [1]\n\nTwo [1]']

@async_test
async def test_repair_preserves_already_emitted_prefix(monkeypatch):
    calls=[]
    async def generate(state):
        calls.append(state.get('answer',''))
        if len(calls)==1:
            yield 'Approved [1]'
            yield 'Invalid [99]'
        else:
            yield 'Repaired [1]'
    async def verify(state,text): return {'ok':True}
    monkeypatch.setattr(blocks,'answer_blocks',generate)
    monkeypatch.setattr(blocks,'verify_answer_async',verify)
    events=[e async for e in blocks.verified_blocks({'intent':'course_qa','citations':[{}]})]
    assert [e['data']['text'] for e in events]==['Approved [1]','\n\nRepaired [1]']
    assert calls==['','Approved [1]']

@async_test
async def test_provider_failure_does_not_claim_missing_evidence_or_retry(monkeypatch):
    calls=[]
    async def generate(state):
        calls.append(1)
        raise TimeoutError('provider overloaded')
        yield
    monkeypatch.setattr(blocks,'answer_blocks',generate)
    state={'intent':'course_qa','citations':[{}]}
    events=[e async for e in blocks.verified_blocks(state)]
    assert calls==[1]
    assert state['finish_reason']=='provider_unavailable'
    assert 'quá tải' in events[0]['data']['text']
