"""Chat học tập: authorization, payload chuẩn bị, persistence và stream."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models.chat import ChatMessage, ChatSession
from app.models.course import Course, Enrollment, Lesson
from app.models.quiz import QuizAttempt
from app.services import chat_transport
from app.services.chat_access import (
    active_attempts,
    context_key,
    require_chat_access,
)
from app.services.chat_payload import (
    ChatSessionSnapshot,
    snapshot_session,
    title_from,
)
from app.services.chat_payload import (
    history as chat_history,
)
from app.services.chat_payload import (
    payload as build_payload,
)

chatbot_ready = chat_transport.ready
chatbot_error_stream = chat_transport.error_stream


async def close_chatbot_client() -> None:
    await chat_transport.close_client()


async def _persist_assistant(
    db: AsyncSession,
    *,
    session: ChatSession,
    answer: str,
    citations: list[dict],
    intent: str | None,
) -> ChatMessage:
    message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=answer,
        citations=citations,
        intent=intent,
    )
    db.add(message)
    if session.title in ("", "Phiên mới"):
        first = (
            await db.execute(
                select(ChatMessage.content)
                .where(
                    ChatMessage.session_id == session.id,
                    ChatMessage.role == "student",
                )
                .order_by(ChatMessage.created_at)
                .limit(1)
            )
        ).scalar_one_or_none()
        if first:
            session.title = title_from(first)
    session.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()
    await db.refresh(message)
    return message


async def ensure_access_in_db(
    check: AsyncSession, session: ChatSession | ChatSessionSnapshot
) -> None:
    enrolled = (
        await check.execute(
            select(Enrollment.id)
            .join(Course, Course.id == Enrollment.course_id)
            .where(
                Enrollment.course_id == session.course_id,
                Enrollment.student_id == session.student_id,
                Enrollment.status == "active",
                Course.status == "published",
            )
        )
    ).scalar_one_or_none()
    if enrolled is None:
        raise HTTPException(403, detail="Khóa học không còn khả dụng")
    await require_chat_access(check, session.course_id, session.student_id)

    attempt_status = None
    if session.quiz_attempt_id:
        attempt = await check.get(QuizAttempt, session.quiz_attempt_id)
        if attempt is None:
            raise HTTPException(403, detail="Lượt làm bài không còn khả dụng")
        attempt_status = attempt.status
    elif await active_attempts(check, session.course_id, session.student_id):
        raise HTTPException(
            403,
            detail=(
                "Bạn đã bắt đầu bài tập. Vui lòng gửi lại câu hỏi để dùng "
                "ngữ cảnh mới."
            ),
        )
    key = context_key(
        lesson_id=session.lesson_id,
        attempt_id=session.quiz_attempt_id,
        attempt_status=attempt_status,
    )
    if key != session.context_key:
        raise HTTPException(
            403, detail="Ngữ cảnh bài tập đã thay đổi. Vui lòng gửi lại câu hỏi."
        )


async def _ensure_access(session: ChatSession | ChatSessionSnapshot) -> None:
    async with SessionLocal() as check:
        await ensure_access_in_db(check, session)


async def prepare_stream(
    db: AsyncSession,
    *,
    course: Course,
    session: ChatSession,
    message: str,
    lesson: Lesson | None,
    module_title: str | None,
    quiz: dict | None,
    attempt: QuizAttempt | None,
    support_mode: str,
    draft_answers: dict[str, list[str]] | None = None,
) -> tuple[dict, ChatSessionSnapshot]:
    history = await chat_history(db, session.id)
    payload = build_payload(
        course=course,
        session=session,
        message=message,
        history_messages=history,
        lesson=lesson,
        module_title=module_title,
        quiz=quiz,
        attempt=attempt,
        support_mode=support_mode,
        draft_answers=draft_answers,
    )
    db.add(
        ChatMessage(
            session_id=session.id,
            role="student",
            content=message,
            citations=[],
            intent=None,
        )
    )
    await db.commit()
    return payload, snapshot_session(session)


async def stream_in_session(
    *,
    session_id: str,
    payload: dict,
    session_snapshot: ChatSessionSnapshot,
) -> AsyncIterator[str]:
    if not chatbot_ready():
        yield chat_transport.sse("error", {"message": "Trợ lý học tập chưa được cấu hình"})
        return

    yield chat_transport.sse("session", {"sessionId": session_id})

    answer_parts: list[str] = []
    citations: list[dict] = []
    intent: str | None = None
    completed = False

    async def ensure_access() -> None:
        await _ensure_access(session_snapshot)

    try:
        async for event, data in chat_transport.stream_events(payload, ensure_access):
            if event == "token":
                answer_parts.append(data.get("text") or "")
            elif event == "citations":
                citations = data.get("citations") or []
            elif event == "done":
                intent = data.get("intent")
                completed = True
            yield chat_transport.sse(event, data)
    except (httpx.HTTPError, RuntimeError, ValueError):
        yield chat_transport.sse(
            "error",
            {"message": "Trợ lý học tập tạm thời không phản hồi"},
        )
        return

    if completed:
        async with SessionLocal() as db:
            session = await db.get(ChatSession, session_id)
            if session is not None:
                await _persist_assistant(
                    db,
                    session=session,
                    answer="".join(answer_parts),
                    citations=citations,
                    intent=intent,
                )
