"""Chat học tập theo course/lesson version và attempt cụ thể.

Backend là nguồn sự thật cho quyền, ngữ cảnh và lịch sử. Chatbot chỉ truy hồi
trong đúng course version đã publish và không bao giờ nhận answer key trước khi
attempt tương ứng được nộp.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.chat import ChatMessage, ChatSession
from app.models.course import (
    Course,
    CourseVersion,
    Enrollment,
    Lesson,
    LessonVersion,
)
from app.models.quiz import QuizAttempt, QuizSpec
from app.services.chat_access import active_attempts, context_key, require_chat_access

logger = logging.getLogger(__name__)

TITLE_MAX = 60
CONTEXT_MAX = 30000
HISTORY_LIMIT = 10

_chatbot_client: httpx.AsyncClient | None = None


@dataclass(frozen=True)
class ChatSessionSnapshot:
    """Dữ liệu tối thiểu để kiểm tra quyền trong lúc stream.

    Stream có thể kéo dài hàng chục giây; giữ ORM session/connection trong suốt
    thời gian đó sẽ làm cạn pool. Snapshot chỉ chứa scalar đã load sẵn.
    """

    id: str
    student_id: str
    course_id: str
    course_version_id: str | None
    lesson_version_id: str | None
    quiz_attempt_id: str | None
    context_key: str


def snapshot_session(session: ChatSession) -> ChatSessionSnapshot:
    return ChatSessionSnapshot(
        id=session.id,
        student_id=session.student_id,
        course_id=session.course_id,
        course_version_id=session.course_version_id,
        lesson_version_id=session.lesson_version_id,
        quiz_attempt_id=session.quiz_attempt_id,
        context_key=session.context_key,
    )


def question_correct_ids(question: dict) -> list[str]:
    ids = question.get("correctOptionIds")
    if ids is None:
        single = question.get("correctOptionId")
        ids = [single] if single else []
    return [str(item) for item in ids]


def build_assignment_context(
    *,
    course_title: str,
    module_title: str | None,
    lesson_title: str | None,
    quiz: QuizSpec,
    attempt: QuizAttempt | None,
    include_answers: bool,
    draft_answers: dict[str, list[str]] | None = None,
) -> str:
    lines = [
        f"Khóa học: {course_title}",
        f"Chương: {module_title}" if module_title else "",
        f"Bài học: {lesson_title}" if lesson_title else "",
        f"Bài tập: {lesson_title or ''}",
        f"Số câu hỏi: {len(quiz.questions)}",
    ]
    lines = [line for line in lines if line]
    if quiz.instructions.strip():
        lines.append(f"Hướng dẫn: {quiz.instructions.strip()}")

    answers = (attempt.answers if attempt is not None else draft_answers) or {}
    for index, question in enumerate(quiz.questions, start=1):
        lines.append(f"Câu {index}: {question['prompt']}")
        for option in question["options"]:
            lines.append(f"- {option['id']}: {option['text']}")
        selected = answers.get(question["id"]) or []
        if isinstance(selected, str):
            selected = [selected]
        lines.append(
            f"Học viên chọn: {', '.join(selected) if selected else 'chưa trả lời'}"
        )
        if include_answers:
            lines.append(
                f"Đáp án đúng: {', '.join(question_correct_ids(question))}"
            )
            lines.append(f"Giải thích: {question.get('explanation', '')}")
    context = "\n".join(lines)
    if len(context) > CONTEXT_MAX:
        raise HTTPException(
            422,
            detail=(
                "Ngữ cảnh bài tập vượt giới hạn 30.000 ký tự; cần rút gọn đề "
                "để gửi đầy đủ."
            ),
        )
    return context


def _title_from(message: str) -> str:
    text = " ".join(message.split())
    if len(text) <= TITLE_MAX:
        return text or "Phiên mới"
    return text[: TITLE_MAX - 1].rstrip() + "…"


def _chatbot_ready() -> bool:
    return bool(settings.chatbot_url_resolved and settings.chatbot_internal_token)


def chatbot_ready() -> bool:
    """Public guard để route quyết định trước khi ghi message vào DB."""
    return _chatbot_ready()


def _headers() -> dict[str, str]:
    return {"X-Chatbot-Token": settings.chatbot_internal_token}


def _client() -> httpx.AsyncClient:
    global _chatbot_client
    if _chatbot_client is None:
        _chatbot_client = httpx.AsyncClient(
            timeout=settings.chatbot_timeout_seconds,
            headers=_headers(),
        )
    return _chatbot_client


async def close_chatbot_client() -> None:
    global _chatbot_client
    if _chatbot_client is not None:
        await _chatbot_client.aclose()
        _chatbot_client = None


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def chatbot_error_stream(message: str) -> AsyncIterator[str]:
    """SSE lỗi không cần DB (dùng khi chatbot chưa cấu hình)."""
    yield _sse("error", {"message": message})


async def _history(db: AsyncSession, session_id: str) -> list[dict]:
    rows = (
        (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.desc())
                .limit(HISTORY_LIMIT)
            )
        )
        .scalars()
        .all()
    )
    return [
        {"role": message.role, "content": message.content}
        for message in reversed(rows)
    ]


def _payload(
    *,
    course: Course,
    course_version: CourseVersion,
    session: ChatSession,
    message: str,
    history: list[dict],
    lesson: Lesson | None,
    lesson_version: LessonVersion | None,
    module_title: str | None,
    quiz: QuizSpec | None,
    attempt: QuizAttempt | None,
    support_mode: str,
    draft_answers: dict[str, list[str]] | None = None,
) -> dict:
    context = ""
    if quiz is not None and lesson_version is not None:
        context = build_assignment_context(
            course_title=course_version.title,
            module_title=module_title,
            lesson_title=lesson_version.title,
            quiz=quiz,
            attempt=attempt,
            include_answers=support_mode == "review",
            draft_answers=draft_answers,
        )
    return {
        "message": message,
        "course_id": course.id,
        "course_version_id": course_version.id,
        "thread_id": session.id,
        "context_key": session.context_key,
        "history": history,
        "lesson_id": lesson.id if lesson is not None else None,
        "lesson_version_id": lesson_version.id if lesson_version else None,
        "lesson_title": lesson_version.title if lesson_version else "",
        "module_title": module_title or "",
        "attempt_id": attempt.id if attempt is not None else None,
        "assignment_title": lesson_version.title if lesson_version else "",
        "assignment_context": context,
        "support_mode": support_mode,
    }


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
            session.title = _title_from(first)
    session.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()
    await db.refresh(message)
    return message


async def _ensure_access(session: ChatSession | ChatSessionSnapshot) -> None:
    async with SessionLocal() as check:
        await ensure_access_in_db(check, session)


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
                Course.archived_at.is_(None),
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
        course_version_id=session.course_version_id,
        lesson_version_id=session.lesson_version_id,
        attempt_id=session.quiz_attempt_id,
        attempt_status=attempt_status,
    )
    if key != session.context_key:
        raise HTTPException(
            403, detail="Ngữ cảnh bài tập đã thay đổi. Vui lòng gửi lại câu hỏi."
        )


async def _guarded_lines(
    response: httpx.Response, session: ChatSession | ChatSessionSnapshot
) -> AsyncIterator[str]:
    lines = response.aiter_lines().__aiter__()
    pending = asyncio.create_task(anext(lines))
    try:
        while True:
            done, _ = await asyncio.wait({pending}, timeout=5)
            if not done:
                await _ensure_access(session)
                yield ": heartbeat"
                continue
            try:
                line = pending.result()
            except StopAsyncIteration:
                return
            yield line
            pending = asyncio.create_task(anext(lines))
    finally:
        pending.cancel()
        with suppress(asyncio.CancelledError, StopAsyncIteration):
            await pending


async def prepare_stream(
    db: AsyncSession,
    *,
    course: Course,
    course_version: CourseVersion,
    session: ChatSession,
    message: str,
    lesson: Lesson | None,
    lesson_version: LessonVersion | None,
    module_title: str | None,
    quiz: QuizSpec | None,
    attempt: QuizAttempt | None,
    support_mode: str,
    draft_answers: dict[str, list[str]] | None = None,
) -> tuple[dict, ChatSessionSnapshot]:
    """Chuẩn bị payload + lưu câu hỏi trong một transaction ngắn.

    Route gọi hàm này rồi đóng DB session trước khi trả StreamingResponse.
    Nhờ vậy connection không bị giữ trong suốt thời gian LLM trả lời.
    """
    history = await _history(db, session.id)
    payload = _payload(
        course=course,
        course_version=course_version,
        session=session,
        message=message,
        history=history,
        lesson=lesson,
        lesson_version=lesson_version,
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
    """Stream SSE từ chatbot mà không giữ DB connection.

    Chỉ mở SessionLocal ngắn khi cần lưu câu trả lời cuối cùng.
    """
    if not _chatbot_ready():
        yield _sse("error", {"message": "Trợ lý học tập chưa được cấu hình"})
        return

    yield _sse("session", {"sessionId": session_id})

    answer_parts: list[str] = []
    citations: list[dict] = []
    intent: str | None = None
    completed = False

    try:
        async with _client().stream(
            "POST",
            f"{settings.chatbot_url_resolved.rstrip('/')}/chat/stream",
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in _guarded_lines(response, session_snapshot):
                if line.startswith("event: "):
                    event = line[7:].strip()
                    continue
                if not line.startswith("data: "):
                    continue
                data = json.loads(line[6:])
                if event == "token":
                    answer_parts.append(data.get("text") or "")
                elif event == "citations":
                    citations = data.get("citations") or []
                elif event == "done":
                    intent = data.get("intent")
                    completed = True
                yield _sse(event, data)
    except (httpx.HTTPError, ValueError):
        yield _sse(
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
