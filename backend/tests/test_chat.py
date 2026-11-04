import asyncio

from sqlalchemy import text

from app.api.routes import chat as chat_routes
from app.db.session import SessionLocal
from app.services import embedding, study_chat
from tests.conftest import auth, login, make_user


def _setup(client):
    asyncio.run(make_user("chat-teacher@test.vn", "teacher"))
    asyncio.run(make_user("chat-student@test.vn", "student"))
    asyncio.run(make_user("chat-outsider@test.vn", "student"))
    teacher = login(client, "chat-teacher@test.vn")
    student = login(client, "chat-student@test.vn")
    outsider = login(client, "chat-outsider@test.vn")
    course = client.post(
        "/teacher/courses",
        headers=auth(teacher),
        json={"title": "Chat course", "status": "published"},
    ).json()
    module = client.post(
        f"/teacher/courses/{course['id']}/modules",
        headers=auth(teacher),
        json={"title": "Module"},
    ).json()
    lesson = client.post(
        f"/teacher/modules/{module['id']}/lessons",
        headers=auth(teacher),
        json={"title": "Lesson"},
    ).json()
    enroll = client.post(f"/api/courses/{course['id']}/enroll", headers=auth(student))
    assert enroll.status_code == 201, enroll.text
    return teacher, student, outsider, course["id"], module["id"], lesson["id"]


def _fake_reply():
    return {
        "answer": "Khóa chính xác định duy nhất mỗi hàng [1].",
        "citations": [
            {
                "document_id": "slide-1",
                "title": "Chương 1 - Bài 1",
                "location": "/media/slide-1.jpg",
                "lesson_id": "lesson-1",
                "lesson_title": "Bài 1",
                "slide_id": "slide-1",
                "slide_index": 1,
                "image_url": "/media/slide-1.jpg",
                "snippet": "Khóa chính xác định duy nhất mỗi hàng.",
                "score": 0.9,
            }
        ],
        "intent": "course_qa",
        "verified": True,
    }


def test_chat_requires_enrollment(client):
    _, _, outsider, course_id, _, _ = _setup(client)
    response = client.post(
        f"/api/courses/{course_id}/chat",
        headers=auth(outsider),
        json={"message": "Khóa chính là gì?"},
    )
    assert response.status_code == 403


def test_chat_session_crud(client, monkeypatch):
    _, student, _, course_id, _, lesson_id = _setup(client)

    async def fake_ask(_payload):
        return _fake_reply()

    monkeypatch.setattr(study_chat, "_ask_chatbot", fake_ask)

    created = client.post(
        f"/api/courses/{course_id}/chat",
        headers=auth(student),
        json={"message": "Khóa chính là gì?", "lessonId": lesson_id},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    session_id = body["sessionId"]
    assert body["answer"].startswith("Khóa chính")
    assert body["citations"][0]["documentId"] == "slide-1"
    assert body["verified"] is True

    sessions = client.get(f"/api/courses/{course_id}/chat/sessions", headers=auth(student))
    assert sessions.status_code == 200
    assert len(sessions.json()) == 1
    assert sessions.json()[0]["messageCount"] == 2

    messages = client.get(f"/api/chat/sessions/{session_id}/messages", headers=auth(student))
    assert messages.status_code == 200
    assert [item["role"] for item in messages.json()] == ["student", "assistant"]
    assert messages.json()[1]["citations"][0]["documentId"] == "slide-1"

    renamed = client.patch(
        f"/api/chat/sessions/{session_id}",
        headers=auth(student),
        json={"title": "Phiên mới"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Phiên mới"

    deleted = client.delete(f"/api/chat/sessions/{session_id}", headers=auth(student))
    assert deleted.status_code == 200
    assert client.get(f"/api/courses/{course_id}/chat/sessions", headers=auth(student)).json() == []


def test_chat_hints_do_not_include_answers(client, monkeypatch):
    teacher, student, _, course_id, module_id, _ = _setup(client)
    item = client.post(
        f"/teacher/modules/{module_id}/quizzes",
        headers=auth(teacher),
        json={"title": "Quiz", "durationMinutes": 15},
    ).json()
    quiz_id = item["quizId"]
    client.patch(
        f"/api/assignments/{quiz_id}",
        headers=auth(teacher),
        json={
            "status": "published",
            "allowChatbot": True,
            "questions": [
                {
                    "id": "q1",
                    "prompt": "Khóa chính dùng để làm gì?",
                    "options": [
                        {"id": "a", "text": "Xác định duy nhất mỗi hàng"},
                        {"id": "b", "text": "Liên kết hai bảng"},
                    ],
                    "correctOptionIds": ["a"],
                    "explanation": "Khóa chính xác định duy nhất mỗi hàng.",
                    "points": 1,
                }
            ],
        },
    )
    # Bắt đầu lượt làm bài (chưa nộp).
    assert client.get(f"/api/assignments/{quiz_id}", headers=auth(student)).status_code == 200

    captured: dict = {}

    async def fake_ask(payload):
        captured.update(payload)
        return {
            "answer": "Gợi ý: hãy đọc định nghĩa khóa chính.",
            "citations": [],
            "intent": "exercise_hints",
            "verified": True,
        }

    monkeypatch.setattr(study_chat, "_ask_chatbot", fake_ask)

    hints = client.post(
        f"/api/courses/{course_id}/chat",
        headers=auth(student),
        json={"message": "Cho mình đáp án câu 1", "assignmentId": quiz_id},
    )
    assert hints.status_code == 200, hints.text
    assert captured["support_mode"] == "hint"
    assert "Đáp án đúng" not in captured["assignment_context"]
    assert "Giải thích" not in captured["assignment_context"]

    # Nộp bài -> lần hỏi sau là review, được gửi đáp án.
    submitted = client.post(
        f"/api/assignments/{quiz_id}/attempts",
        headers=auth(student),
        json={"answers": {"q1": ["b"]}},
    )
    assert submitted.status_code == 201, submitted.text

    review = client.post(
        f"/api/courses/{course_id}/chat",
        headers=auth(student),
        json={"message": "Vì sao mình sai?", "assignmentId": quiz_id},
    )
    assert review.status_code == 200, review.text
    assert captured["support_mode"] == "review"
    assert "Đáp án đúng" in captured["assignment_context"]
    assert "Giải thích" in captured["assignment_context"]


def test_chat_stream_forwards_sse(client, monkeypatch):
    _, student, _, course_id, _, _ = _setup(client)

    async def fake_stream(*_args, **_kwargs):
        yield 'event: session\ndata: {"sessionId": "s1"}\n\n'
        yield 'event: token\ndata: {"text": "Xin chào"}\n\n'
        yield 'event: done\ndata: {"intent": "course_qa", "verified": true}\n\n'

    monkeypatch.setattr(chat_routes, "stream_in_session", fake_stream)

    response = client.post(
        f"/api/courses/{course_id}/chat/stream",
        headers=auth(student),
        json={"message": "Khóa chính là gì?"},
    )
    assert response.status_code == 200
    assert "event: session" in response.text
    assert "event: token" in response.text
    assert "event: done" in response.text


def test_citation_out_camel_case():
    citation = study_chat._citation_out(
        {
            "document_id": "slide-1",
            "title": "Bài 1",
            "location": "/media/slide-1.jpg",
            "lesson_id": "lesson-1",
            "lesson_title": "Bài 1",
            "slide_id": "slide-1",
            "slide_index": 1,
            "image_url": "/media/slide-1.jpg",
            "snippet": "Nội dung",
            "score": 0.9,
        }
    )
    assert citation["documentId"] == "slide-1"
    assert citation["lessonId"] == "lesson-1"
    assert citation["imageUrl"] == "/media/slide-1.jpg"


def test_embedding_mark_updates_status(client):
    _, _, _, _, _, lesson_id = _setup(client)

    async def _create_slide():
        async with SessionLocal() as session:
            slide_id = (
                await session.execute(
                    text(
                        """
                        INSERT INTO lesson_contents
                            (lesson_id, order_index, image_url, content_json)
                        VALUES (:lesson_id, 1, '/media/test.jpg', '{}'::jsonb)
                        RETURNING id
                        """
                    ),
                    {"lesson_id": lesson_id},
                )
            ).scalar_one()
            await session.commit()
            return str(slide_id)

    slide_id = asyncio.run(_create_slide())

    async def _mark_ready():
        async with SessionLocal() as session:
            await embedding._mark(session, slide_id, embedding.READY)

    asyncio.run(_mark_ready())

    async def _status():
        async with SessionLocal() as session:
            return (
                await session.execute(
                    text("SELECT embedding_status FROM lesson_contents WHERE id = :id"),
                    {"id": slide_id},
                )
            ).scalar_one()

    assert asyncio.run(_status()) == embedding.READY


def _quiz(client, teacher, module_id, *, allowed=False):
    created = client.post(
        f"/teacher/modules/{module_id}/quizzes",
        headers=auth(teacher),
        json={"title": "Quiz", "durationMinutes": 15},
    )
    assert created.status_code == 201, created.text
    quiz_id = created.json()["quizId"]
    questions = [
        {
            "id": f"q{i}",
            "prompt": f"Câu hỏi {i}?",
            "options": [{"id": "a", "text": "Phương án A"}, {"id": "b", "text": "Phương án B"}],
            "correctOptionIds": ["a"],
            "explanation": "EXPLANATION_SECRET",
            "points": 1,
        }
        for i in range(1, 11)
    ]
    response = client.patch(
        f"/api/assignments/{quiz_id}",
        headers=auth(teacher),
        json={
            "status": "published",
            "allowChatbot": allowed,
            "allowRetry": True,
            "questions": questions,
        },
    )
    assert response.status_code == 200, response.text
    return quiz_id


def _sql(sql, params):
    async def run():
        async with SessionLocal() as db:
            await db.execute(text(sql), params)
            await db.commit()

    asyncio.run(run())


def test_course_wide_lock_history_stream_and_unlock(client, monkeypatch):
    teacher, student, _, course, module, lesson = _setup(client)

    async def ask(payload):
        return _fake_reply()

    monkeypatch.setattr(study_chat, "_ask_chatbot", ask)
    old = client.post(
        f"/api/courses/{course}/chat", headers=auth(student), json={"message": "hello"}
    ).json()
    quiz = _quiz(client, teacher, module)
    before = client.get(f"/api/courses/{course}/chat/access", headers=auth(student)).json()
    assert before == {"allowed": True, "reason": None, "blockedUntil": None}
    client.get(f"/api/assignments/{quiz}", headers=auth(student))
    locked = client.get(f"/api/courses/{course}/chat/access", headers=auth(student)).json()
    assert locked["allowed"] is False and locked["blockedUntil"] and locked["reason"]
    for suffix in ["chat", "chat/stream"]:
        # Omitting assignment id, changing lesson or reusing a session cannot bypass the lock.
        for extra in [
            {},
            {"assignmentId": quiz},
            {"lessonId": lesson, "sessionId": old["sessionId"]},
        ]:
            assert (
                client.post(
                    f"/api/courses/{course}/{suffix}",
                    headers=auth(student),
                    json={"message": "help", **extra},
                ).status_code
                == 403
            )
    assert (
        client.get(f"/api/courses/{course}/chat/sessions", headers=auth(student)).status_code == 403
    )
    assert (
        client.get(
            f"/api/chat/sessions/{old['sessionId']}/messages", headers=auth(student)
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/assignments/{quiz}/attempts", headers=auth(student), json={"answers": {}}
        ).status_code
        == 201
    )
    assert (
        client.get(f"/api/courses/{course}/chat/access", headers=auth(student)).json()["allowed"]
        is True
    )
    client.post(f"/api/assignments/{quiz}/retry", headers=auth(student))
    assert (
        client.get(f"/api/courses/{course}/chat/access", headers=auth(student)).json()["allowed"]
        is False
    )


def test_multiple_attempts_deadlines_and_course_isolation(client):
    from datetime import datetime, timezone

    teacher, student, _, course, module, _ = _setup(client)
    first, second = _quiz(client, teacher, module), _quiz(client, teacher, module)
    for quiz in (first, second):
        client.get(f"/api/assignments/{quiz}", headers=auth(student))
    # First ends by duration; second ends by due date, both at the boundary.
    _sql(
        "UPDATE quiz_attempt_sessions SET started_at = now() - interval '15 minutes' WHERE assignment_id = :id",
        {"id": first},
    )
    assert not client.get(f"/api/courses/{course}/chat/access", headers=auth(student)).json()[
        "allowed"
    ]
    _sql(
        "UPDATE quiz_assignments SET due_at = :now WHERE id = :id",
        {"id": second, "now": datetime.now(timezone.utc)},
    )
    assert client.get(f"/api/courses/{course}/chat/access", headers=auth(student)).json()["allowed"]
    # A new blocked attempt in this course does not affect a different enrollment.
    third = _quiz(client, teacher, module)
    client.get(f"/api/assignments/{third}", headers=auth(student))
    other = client.post(
        "/teacher/courses", headers=auth(teacher), json={"title": "Other", "status": "published"}
    ).json()["id"]
    client.post(f"/api/courses/{other}/enroll", headers=auth(student))
    assert client.get(f"/api/courses/{other}/chat/access", headers=auth(student)).json()["allowed"]
    assert not client.get(f"/api/courses/{course}/chat/access", headers=auth(student)).json()[
        "allowed"
    ]


def test_drafts_complete_context_review_and_retry_history(client, monkeypatch):
    teacher, student, _, course, module, _ = _setup(client)
    quiz = _quiz(client, teacher, module, allowed=True)
    client.get(f"/api/assignments/{quiz}", headers=auth(student))
    captured = []

    async def ask(payload):
        captured.append(payload)
        return _fake_reply()

    monkeypatch.setattr(study_chat, "_ask_chatbot", ask)

    def chat(**extra):
        return client.post(
            f"/api/courses/{course}/chat",
            headers=auth(student),
            json={"message": "Gợi ý câu cuối", "assignmentId": quiz, **extra},
        )

    first = chat(draftAnswers={"q1": ["b"], "q5": ["a"], "q10": ["b"]})
    assert first.status_code == 200, first.text
    context = captured[-1]["assignment_context"]
    assert "Câu 10: Câu hỏi 10?" in context and "Học viên chọn: b" in context
    assert "EXPLANATION_SECRET" not in context and "Đáp án đúng" not in context
    assert chat(draftAnswers={"other": ["a"]}).status_code == 400
    assert chat(draftAnswers={"q1": ["other"]}).status_code == 400
    again = chat(sessionId=first.json()["sessionId"], draftAnswers={"q10": ["a"]})
    assert again.status_code == 200
    assert captured[-1]["history"] and captured[-1]["assignment_context"].endswith(
        "Học viên chọn: a"
    )
    assert client.get(f"/api/assignments/{quiz}/attempt", headers=auth(student)).json() is None
    client.post(
        f"/api/assignments/{quiz}/attempts", headers=auth(student), json={"answers": {"q10": ["b"]}}
    )
    review = chat(sessionId=first.json()["sessionId"], draftAnswers={"q10": ["a"]})
    assert review.status_code == 200, review.text
    assert captured[-1]["support_mode"] == "review" and captured[-1]["history"] == []
    assert "Học viên chọn: b\nĐáp án đúng: a" in captured[-1]["assignment_context"]
    client.post(f"/api/assignments/{quiz}/retry", headers=auth(student))
    assert chat(sessionId=review.json()["sessionId"]).status_code == 404
    assert chat().status_code == 200
    assert captured[-1]["history"] == [] and captured[-1]["support_mode"] == "hint"


def test_only_course_manager_can_change_chatbot_flag(client):
    teacher, student, outsider, _, module, _ = _setup(client)
    quiz = _quiz(client, teacher, module)
    assert (
        client.get(f"/api/assignments/{quiz}", headers=auth(teacher)).json()["allowChatbot"]
        is False
    )
    for user in (student, outsider):
        assert (
            client.patch(
                f"/api/assignments/{quiz}", headers=auth(user), json={"allowChatbot": True}
            ).status_code
            == 403
        )
    asyncio.run(make_user("other-teacher@test.vn", "teacher"))
    other = login(client, "other-teacher@test.vn")
    assert (
        client.patch(
            f"/api/assignments/{quiz}", headers=auth(other), json={"allowChatbot": True}
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/assignments/{quiz}", headers=auth(teacher), json={"allowChatbot": True}
        ).json()["allowChatbot"]
        is True
    )


def test_revocation_during_generation_discards_reply(client, monkeypatch):
    teacher, student, _, course, module, _ = _setup(client)
    quiz = _quiz(client, teacher, module, allowed=True)
    client.get(f"/api/assignments/{quiz}", headers=auth(student))

    async def ask(payload):
        async with SessionLocal() as db:
            await db.execute(
                text("UPDATE quiz_assignments SET allow_chatbot = false WHERE id = :id"),
                {"id": quiz},
            )
            await db.commit()
        return _fake_reply()

    monkeypatch.setattr(study_chat, "_ask_chatbot", ask)
    response = client.post(
        f"/api/courses/{course}/chat", headers=auth(student), json={"message": "help"}
    )
    assert response.status_code == 403


def test_context_overflow_rejected_without_truncation():
    from types import SimpleNamespace

    import pytest
    from fastapi import HTTPException

    assignment = SimpleNamespace(
        title="quiz",
        instructions="",
        questions=[
            {"id": f"q{i}", "prompt": "P" * 4000, "options": [{"id": "a", "text": "A"}]}
            for i in range(10)
        ],
    )
    with pytest.raises(HTTPException, match="422"):
        study_chat.build_assignment_context(
            SimpleNamespace(title="course"), None, None, assignment, None, include_answers=False
        )


def test_stream_revocation_emits_error_before_next_token(client, monkeypatch):
    import httpx

    teacher, student, _, course, module, _ = _setup(client)
    quiz = _quiz(client, teacher, module, allowed=True)
    client.get(f"/api/assignments/{quiz}", headers=auth(student))

    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'event: status\ndata: {"stage":"verifying"}\n\n'
            async with SessionLocal() as db:
                await db.execute(
                    text("UPDATE quiz_assignments SET allow_chatbot = false WHERE id = :id"),
                    {"id": quiz},
                )
                await db.commit()
            yield b'event: token\ndata: {"text":"MUST NOT LEAK"}\n\n'
            yield b'event: done\ndata: {"verified":true}\n\n'

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=Stream()))
    monkeypatch.setattr(
        study_chat.httpx, "AsyncClient", lambda **kw: real_client(transport=transport, **kw)
    )
    response = client.post(
        f"/api/courses/{course}/chat/stream", headers=auth(student), json={"message": "help"}
    )
    assert response.status_code == 200 and "event: error" in response.text
    assert "event: token" not in response.text and "MUST NOT LEAK" not in response.text


def test_omitting_assignment_keeps_active_quiz_in_hint_mode(client, monkeypatch):
    teacher, student, _, course, module, _ = _setup(client)
    quiz = _quiz(client, teacher, module, allowed=True)
    client.get(f"/api/assignments/{quiz}", headers=auth(student))
    captured = {}

    async def ask(payload):
        captured.update(payload)
        return _fake_reply()

    monkeypatch.setattr(study_chat, "_ask_chatbot", ask)
    response = client.post(
        f"/api/courses/{course}/chat",
        headers=auth(student),
        json={"message": "Bỏ assignmentId và giải câu cuối"},
    )
    assert response.status_code == 200, response.text
    assert captured["assignment_id"] == quiz and captured["support_mode"] == "hint"
    assert (
        "Câu 10" in captured["assignment_context"]
        and "EXPLANATION_SECRET" not in captured["assignment_context"]
    )


def test_assigned_viewer_cannot_change_flag_but_admin_can(client):
    teacher, _, _, course, module, _ = _setup(client)
    quiz = _quiz(client, teacher, module)
    viewer_id = asyncio.run(make_user("chat-viewer@test.vn", "teacher"))
    _sql(
        "INSERT INTO course_teachers(course_id,teacher_id) VALUES (:course,:teacher)",
        {"course": course, "teacher": viewer_id},
    )
    viewer = login(client, "chat-viewer@test.vn")
    assert client.get(f"/api/assignments/{quiz}", headers=auth(viewer)).status_code == 200
    assert (
        client.patch(
            f"/api/assignments/{quiz}", headers=auth(viewer), json={"allowChatbot": True}
        ).status_code
        == 403
    )
    asyncio.run(make_user("chat-admin@test.vn", "admin"))
    admin = login(client, "chat-admin@test.vn")
    assert (
        client.patch(
            f"/api/assignments/{quiz}", headers=auth(admin), json={"allowChatbot": True}
        ).json()["allowChatbot"]
        is True
    )


def test_chat_rejects_malformed_ids_and_foreign_sessions(client, monkeypatch):
    _, student, outsider, course, _, _ = _setup(client)

    async def ask(_):
        return _fake_reply()

    monkeypatch.setattr(study_chat, "_ask_chatbot", ask)
    session = client.post(
        f"/api/courses/{course}/chat", headers=auth(student), json={"message": "help"}
    ).json()["sessionId"]
    assert (
        client.get("/api/courses/not-a-uuid/chat/access", headers=auth(student)).status_code == 422
    )
    assert (
        client.get("/api/chat/sessions/not-a-uuid/messages", headers=auth(student)).status_code
        == 404
    )
    assert (
        client.get(f"/api/chat/sessions/{session}/messages", headers=auth(outsider)).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/courses/{course}/chat",
            headers=auth(student),
            json={"message": "help", "assignmentId": "not-a-uuid"},
        ).status_code
        == 422
    )


def test_reader_session_continues_across_lessons(client, monkeypatch):
    teacher, student, _, course, module, first_lesson = _setup(client)
    second = client.post(f"/teacher/modules/{module}/lessons", headers=auth(teacher), json={"title": "Second"}).json()["id"]
    payloads = []

    async def ask(payload):
        payloads.append(payload)
        return _fake_reply()

    monkeypatch.setattr(study_chat, "_ask_chatbot", ask)
    session_id = None
    for lesson in [first_lesson, first_lesson, second]:
        reply = client.post(f"/api/courses/{course}/chat", headers=auth(student), json={"message": "Giải thích tiếp", "lessonId": lesson, "sessionId": session_id})
        assert reply.status_code == 200, reply.text
        if session_id:
            assert reply.json()["sessionId"] == session_id
        session_id = reply.json()["sessionId"]
    sessions = client.get(f"/api/courses/{course}/chat/sessions", headers=auth(student)).json()
    assert len(sessions) == 1
    assert sessions[0]["messageCount"] == 6
    assert sessions[0]["canContinue"] is True
    assert len(payloads[-1]["history"]) == 4
