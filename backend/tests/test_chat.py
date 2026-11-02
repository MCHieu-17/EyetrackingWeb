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

    sessions = client.get(
        f"/api/courses/{course_id}/chat/sessions", headers=auth(student)
    )
    assert sessions.status_code == 200
    assert len(sessions.json()) == 1
    assert sessions.json()[0]["messageCount"] == 2

    messages = client.get(
        f"/api/chat/sessions/{session_id}/messages", headers=auth(student)
    )
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

    deleted = client.delete(
        f"/api/chat/sessions/{session_id}", headers=auth(student)
    )
    assert deleted.status_code == 200
    assert client.get(
        f"/api/courses/{course_id}/chat/sessions", headers=auth(student)
    ).json() == []


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
    assert client.get(
        f"/api/assignments/{quiz_id}", headers=auth(student)
    ).status_code == 200

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
