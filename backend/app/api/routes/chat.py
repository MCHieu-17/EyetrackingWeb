"""API chat học tập theo khóa, bài và attempt cụ thể."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.access import get_course_or_404
from app.api.deps import require_roles, user_rate_limit
from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.models.auth import User
from app.models.chat import ChatMessage, ChatSession
from app.models.course import Enrollment, Lesson
from app.models.quiz import QuizAttempt
from app.schemas.chat import (
    ChatMessageOut,
    ChatSendIn,
    ChatSessionOut,
    ChatSessionUpdate,
)
from app.services.chat_access import chat_access, context_key, require_chat_access
from app.services.chat_context import (
    _latest_attempt,
    _message_count,
    _prepare,
    _require_enrolled,
    _session_or_404,
    _session_out,
)
from app.services.study_chat import (
    chatbot_error_stream,
    chatbot_ready,
    prepare_stream,
    stream_in_session,
)

router = APIRouter(tags=["chat"])

NEW_TITLE = "Phiên mới"


@router.get("/api/courses/{course_id}/chat/access")
async def get_chat_access(
    course_id: UUID,
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_course_or_404(db, str(course_id))
    await _require_enrolled(db, course.id, user)
    return await chat_access(db, course.id, user.id)


@router.get(
    "/api/courses/{course_id}/chat/sessions",
    response_model=list[ChatSessionOut],
)
async def list_sessions(
    course_id: UUID,
    assignment_id: UUID | None = Query(None, alias="assignmentId"),
    attempt_id: UUID | None = Query(None, alias="attemptId"),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_course_or_404(db, str(course_id))
    await _require_enrolled(db, course.id, user)
    await require_chat_access(db, course.id, user.id)

    current_key = None
    if assignment_id is not None:
        lesson = await db.get(Lesson, str(assignment_id))
        if lesson is None or lesson.kind != "quiz":
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài tập"
            )
        enrollment_id = (
            await db.execute(
                select(Enrollment.id).where(
                    Enrollment.course_id == course.id,
                    Enrollment.student_id == user.id,
                )
            )
        ).scalar_one()
        if attempt_id is not None:
            attempt = await db.get(QuizAttempt, str(attempt_id))
            if attempt is None or attempt.enrollment_id != enrollment_id:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lượt làm bài"
                )
        else:
            attempt = await _latest_attempt(db, enrollment_id, lesson.id)
        current_key = context_key(
            lesson_id=lesson.id,
            attempt_id=attempt.id if attempt else None,
            attempt_status=attempt.status if attempt else None,
        )

    stmt = (
        select(ChatSession)
        .where(
            ChatSession.student_id == user.id,
            ChatSession.course_id == course.id,
            ChatSession.archived_at.is_(None),
        )
        .order_by(ChatSession.updated_at.desc())
    )
    if assignment_id is not None:
        stmt = stmt.where(ChatSession.lesson_id == str(assignment_id))
    if attempt_id is not None:
        stmt = stmt.where(ChatSession.quiz_attempt_id == str(attempt_id))
    sessions = (
        await db.execute(stmt.limit(limit).offset(offset))
    ).scalars().all()
    if not sessions:
        return []

    # Chỉ đếm tin nhắn của các session trong page, không aggregate toàn bảng.
    counts = dict(
        (
            await db.execute(
                select(ChatMessage.session_id, func.count(ChatMessage.id))
                .where(ChatMessage.session_id.in_([session.id for session in sessions]))
                .group_by(ChatMessage.session_id)
            )
        ).all()
    )
    out: list[ChatSessionOut] = []
    for session in sessions:
        item = _session_out(session, int(counts.get(session.id, 0)))
        item.can_continue = current_key is None or session.context_key == current_key
        out.append(item)
    return out


@router.post(
    "/api/courses/{course_id}/chat/stream",
    dependencies=[
        Depends(rate_limit(20, 60, "study-chat-stream")),
        Depends(
            user_rate_limit(
                1,
                5,
                "study-chat-stream",
                detail="Bạn gửi tin nhắn quá nhanh.",
            )
        ),
    ],
)
async def stream_message(
    course_id: UUID,
    body: ChatSendIn,
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_course_or_404(db, str(course_id))
    await _require_enrolled(db, course.id, user)
    await require_chat_access(db, course.id, user.id)
    (
        session,
        lesson,
        module_title,
        quiz,
        attempt,
        support_mode,
    ) = await _prepare(db, course, body, user)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    if not chatbot_ready():
        await db.close()
        return StreamingResponse(
            chatbot_error_stream("Trợ lý học tập chưa được cấu hình"),
            media_type="text/event-stream",
            headers=headers,
        )

    payload, snapshot = await prepare_stream(
        db,
        course=course,
        session=session,
        message=body.message,
        lesson=lesson,
        module_title=module_title,
        quiz=quiz,
        attempt=attempt,
        support_mode=support_mode,
        draft_answers=body.draft_answers,
    )
    await db.close()
    return StreamingResponse(
        stream_in_session(
            session_id=snapshot.id,
            payload=payload,
            session_snapshot=snapshot,
        ),
        media_type="text/event-stream",
        headers=headers,
    )


@router.get(
    "/api/chat/sessions/{session_id}/messages",
    response_model=list[ChatMessageOut],
)
async def list_messages(
    session_id: str,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    session = await _session_or_404(db, session_id, user)
    course = await get_course_or_404(db, session.course_id)
    await _require_enrolled(db, course.id, user)
    await require_chat_access(db, course.id, user.id)
    rows = (
        (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session.id)
                .order_by(ChatMessage.created_at)
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return [
        ChatMessageOut(
            id=message.id,
            role=message.role,
            content=message.content,
            citations=message.citations or [],
            intent=message.intent,
            created_at=message.created_at,
        )
        for message in rows
    ]


@router.patch("/api/chat/sessions/{session_id}", response_model=ChatSessionOut)
async def rename_session(
    session_id: str,
    body: ChatSessionUpdate,
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    session = await _session_or_404(db, session_id, user)
    session.title = body.title.strip()
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return _session_out(session, await _message_count(db, session.id))


@router.delete("/api/chat/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    session = await _session_or_404(db, session_id, user)
    await db.execute(
        delete(ChatMessage).where(ChatMessage.session_id == session.id)
    )
    await db.execute(delete(ChatSession).where(ChatSession.id == session.id))
    await db.commit()
    return {"status": "ok"}
