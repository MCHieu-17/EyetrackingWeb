"""Query-count guards cho chat (P3).

Các test này không kiểm tra nội dung response (đã có test_chat.py); chúng chỉ
đảm bảo các endpoint không kéo theo quan hệ ORM nặng ngoài ý muốn:

* ``ChatSession.messages`` (selectin) không được load khi chỉ cần metadata;
* ``Enrollment.course`` (joined) không được kéo cả Course graph khi resolve
  context chat.
"""

from __future__ import annotations

import uuid

import pytest

from app.db.session import SessionLocal, engine
from app.models.chat import ChatMessage, ChatSession
from tests.conftest import create_user, login, seed_course
from tests.query_counter import count_queries


async def _seed_chat_session(
    *, student_id: str, ids: dict[str, str], messages: int = 2
) -> str:
    async with SessionLocal() as db:
        session = ChatSession(
            student_id=student_id,
            course_id=ids["course_id"],
            lesson_id=ids["lesson_id"],
            title="Phiên test",
            context_key="",
        )
        db.add(session)
        await db.flush()
        for index in range(messages):
            db.add(
                ChatMessage(
                    session_id=session.id,
                    role="student" if index % 2 == 0 else "assistant",
                    content=f"tin nhắn {index}",
                )
            )
        await db.commit()
        return session.id


@pytest.mark.asyncio
async def test_list_sessions_query_count(client):
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    await _seed_chat_session(student_id=student_id, ids=ids)

    token = await login(client, student_email)
    headers = {"Authorization": f"Bearer {token}"}

    with count_queries(engine) as counter:
        response = await client.get(
            f"/api/courses/{ids['course_id']}/chat/sessions", headers=headers
        )

    assert response.status_code == 200, response.text
    # 2 auth + course + enrollment + chat access + sessions = 6.
    assert counter.count <= 8, counter.statements


@pytest.mark.asyncio
async def test_list_messages_query_count(client):
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    session_id = await _seed_chat_session(student_id=student_id, ids=ids)

    token = await login(client, student_email)
    headers = {"Authorization": f"Bearer {token}"}

    with count_queries(engine) as counter:
        response = await client.get(
            f"/api/chat/sessions/{session_id}/messages", headers=headers
        )

    assert response.status_code == 200, response.text
    assert len(response.json()) == 2
    # 2 auth + session + course + enrollment + chat access + messages = 7.
    assert counter.count <= 9, counter.statements


@pytest.mark.asyncio
async def test_chat_stream_context_query_count(client):
    """``_resolve_context`` không được kéo Course graph qua Enrollment.course."""
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)

    token = await login(client, student_email)
    headers = {"Authorization": f"Bearer {token}"}

    with count_queries(engine) as counter:
        response = await client.post(
            f"/api/courses/{ids['course_id']}/chat/stream",
            json={"message": "Xin chào", "lessonId": ids["lesson_id"]},
            headers=headers,
        )

    assert response.status_code == 200, response.text
    # 2 auth + course + enrollment + chat access + version + enrollment entity
    # + item + lesson + lesson version + module + insert session = 12.
    # Nếu Enrollment.course bị load kèm, count tăng lên 16+.
    assert counter.count <= 13, counter.statements
