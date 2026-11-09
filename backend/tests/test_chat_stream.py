"""Regression: chat SSE không được giữ DB connection trong lúc stream.

Trước đây route truyền `AsyncSession` của request vào generator và giữ nó suốt
thời gian LLM trả lời. Pool 20 connection => tối đa ~20 chat đồng thời. Test
này khóa hành vi mới: generator chỉ mở SessionLocal ngắn khi lưu câu trả lời.
"""

from __future__ import annotations

import uuid

import pytest

from app.db.session import SessionLocal, engine
from app.models.chat import ChatMessage, ChatSession
from app.services import study_chat
from tests.conftest import create_user, seed_course
from tests.query_counter import count_queries


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        yield "event: token"
        yield 'data: {"text": "Xin chào"}'
        yield "event: citations"
        yield 'data: {"citations": []}'
        yield "event: done"
        yield 'data: {"intent": "answer"}'


class _FakeStream:
    async def __aenter__(self):
        return _FakeResponse()

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeClient:
    def stream(self, *args, **kwargs):
        return _FakeStream()


async def _seed_session() -> tuple[str, study_chat.ChatSessionSnapshot]:
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)

    async with SessionLocal() as db:
        session = ChatSession(
            student_id=student_id,
            course_id=ids["course_id"],
            course_version_id=ids["version_id"],
            lesson_id=ids["lesson_id"],
            lesson_version_id=ids["lesson_version_id"],
            title="Phiên test",
            context_key="ctx",
        )
        db.add(session)
        await db.flush()
        db.add(
            ChatMessage(
                session_id=session.id,
                role="student",
                content="Câu hỏi cũ",
            )
        )
        await db.commit()
        return session.id, study_chat.snapshot_session(session)


@pytest.mark.asyncio
async def test_stream_opens_db_only_for_final_persist(monkeypatch):
    session_id, snapshot = await _seed_session()

    monkeypatch.setattr(study_chat, "_chatbot_ready", lambda: True)
    monkeypatch.setattr(study_chat, "_client", lambda: _FakeClient())

    payload = {"message": "Xin chào", "thread_id": session_id}

    with count_queries(engine) as counter:
        chunks = [
            chunk
            async for chunk in study_chat.stream_in_session(
                session_id=session_id,
                payload=payload,
                session_snapshot=snapshot,
            )
        ]

    assert any("event: token" in chunk for chunk in chunks)
    assert any("event: done" in chunk for chunk in chunks)
    # Chỉ query lúc persist cuối: load session + tìm message đầu + insert/update.
    assert counter.count <= 5, counter.statements

    async with SessionLocal() as db:
        rows = (
            await db.execute(
                ChatMessage.__table__.select().where(
                    ChatMessage.session_id == session_id
                )
            )
        ).all()
    assert any(row.content == "Xin chào" for row in rows)
