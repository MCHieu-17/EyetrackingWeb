import asyncio
from sqlalchemy import select, text
from app.db.session import SessionLocal
from app.models.chat import ChatSession
from app.services import study_chat
from tests.conftest import auth
from tests.test_chat import _setup, _quiz, _fake_reply


def create_session(client, monkeypatch, student, course):
    async def reply(payload): return _fake_reply()
    monkeypatch.setattr(study_chat, '_ask_chatbot', reply)
    response = client.post(f'/api/courses/{course}/chat', headers=auth(student), json={'message':'hello'})
    assert response.status_code == 200, response.text
    sid = response.json()['sessionId']
    async def key():
        async with SessionLocal() as db:
            return (await db.get(ChatSession,sid)).context_key
    return {'session_id': sid, 'context_key': asyncio.run(key())}


def query(client, session, operation, **kw):
    return client.post('/internal/chat/lms-query', headers={'X-Chatbot-Token':'test-chatbot-token'}, json={**session, 'operation':operation, **kw})


def test_internal_auth_and_identity_are_not_llm_controlled(client, monkeypatch):
    _,student,_,course,_,_ = _setup(client)
    session = create_session(client,monkeypatch,student,course)
    assert client.post('/internal/chat/lms-query',json={**session,'operation':'course'}).status_code == 401
    assert query(client,session,'course',student_id='other').status_code == 422
    assert query(client,session,'sql',target='SELECT *').status_code == 422
    assert query(client,{**session,'context_key':'forged'},'course').status_code == 403
    response = query(client,session,'course')
    assert response.status_code == 200
    assert response.json()['course_id'] == course


def test_deadlines_duplicates_drafts_and_unsubmitted_scores(client,monkeypatch):
    teacher,student,_,course,module,_ = _setup(client)
    q1 = _quiz(client,teacher,module,allowed=True)
    q2 = _quiz(client,teacher,module,allowed=True)
    draft = client.post(f'/teacher/modules/{module}/quizzes',headers=auth(teacher),json={'title':'DRAFT_SECRET','durationMinutes':15}).json()
    session = create_session(client,monkeypatch,student,course)
    result = query(client,session,'assignments').json()['assignments']
    assert {x['id'] for x in result} == {q1,q2}
    assert all(x['due_at'] is None and x['remaining_seconds'] is None for x in result)
    ambiguous = query(client,session,'assignment',target='Quiz').json()
    assert len(ambiguous['choices']) == 2
    assert query(client,session,'assignment',target=draft['quizId']).json().get('clarification')
    results = query(client,session,'results').json()['assignments']
    assert all(x['score'] is None for x in results)
    assert 'EXPLANATION_SECRET' not in str(results)
    # Teacher locks chat after request starts: reverse tool must see fresh state.
    client.get(f'/api/assignments/{q1}', headers=auth(student))
    client.patch(f'/api/assignments/{q1}',headers=auth(teacher),json={'allowChatbot':False})
    assert query(client,session,'access').status_code == 403


def test_lms_cannot_read_another_course(client,monkeypatch):
    teacher,student,_,course,module,_ = _setup(client)
    other = client.post('/teacher/courses',headers=auth(teacher),json={'title':'OTHER_SECRET','status':'published'}).json()
    othermod = client.post(f"/teacher/courses/{other['id']}/modules",headers=auth(teacher),json={'title':'M'}).json()
    q = _quiz(client,teacher,othermod['id'],allowed=True)
    session = create_session(client,monkeypatch,student,course)
    response = query(client,session,'assignment',target=q)
    assert response.status_code == 200
    assert response.json()['choices'] == []
    assert 'OTHER_SECRET' not in response.text


def test_effective_attempt_deadline_and_own_scores(client,monkeypatch):
    from datetime import datetime,timedelta,timezone
    teacher,student,outsider,course,module,_=_setup(client)
    q=_quiz(client,teacher,module,allowed=True)
    due=datetime.now(timezone.utc)+timedelta(minutes=3)
    response=client.patch(f'/api/assignments/{q}',headers=auth(teacher),json={'dueAt':due.isoformat()})
    assert response.status_code==200,response.text
    client.get(f'/api/assignments/{q}',headers=auth(student))
    session=create_session(client,monkeypatch,student,course)
    row=query(client,session,'assignment',target=q).json()['assignments'][0]
    assert row['attempt_deadline']==row['due_at']
    assert 0 < row['remaining_seconds'] <= 180
    assert row['status']=='đang làm'
    assert client.post(f'/api/assignments/{q}/attempts',headers=auth(student),json={'answers':{}}).status_code==201
    assert query(client,session,'access').status_code==403 # submission invalidates hint context
    client.post(f'/api/courses/{course}/enroll',headers=auth(outsider))
    client.get(f'/api/assignments/{q}',headers=auth(outsider))
    result=client.post(f'/api/assignments/{q}/attempts',headers=auth(outsider),json={'answers':{f'q{i}':['a'] for i in range(1,11)}})
    assert result.status_code==201,result.text
    session=create_session(client,monkeypatch,student,course)
    own=query(client,session,'results').json()['assignments'][0]
    assert own['score']==0 and own['max_score']==10
