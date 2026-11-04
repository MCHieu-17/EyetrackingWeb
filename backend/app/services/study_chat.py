"""Chat học tập: dựng ngữ cảnh LMS, gọi chatbot service và lưu phiên/tin nhắn.

Backend là nơi dựng ngữ cảnh (khóa > chương > bài > bài tập) và là **nguồn sự
thật** cho lịch sử hiển thị (`chat_sessions`/`chat_messages`). Chatbot service
stateless: backend gửi kèm history trong mỗi request.

Bảo vệ đáp án:
- Trước khi nộp (`support_mode="hint"`): chỉ gửi đề + options + đáp án sinh viên
  đã chọn; KHÔNG gửi đáp án đúng/giải thích.
- Sau khi nộp (`support_mode="review"`): gửi đáp án đúng + giải thích để chữa bài.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import suppress
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.chat import ChatMessage, ChatSession
from app.models.course import Course, Enrollment, Lesson, Module
from app.models.quiz import QuizAssignment, QuizAttempt
from app.services.chat_access import active_assignments, context_key, require_chat_access

logger = logging.getLogger(__name__)

# Độ dài tiêu đề phiên tự sinh từ câu hỏi đầu tiên.
TITLE_MAX = 60

# Trần ngữ cảnh bài tập gửi kèm (khớp giới hạn phía chatbot).
CONTEXT_MAX = 30000

# Số tin nhắn gần nhất gửi kèm làm history.
HISTORY_LIMIT = 10


def question_correct_ids(question: dict) -> list[str]:
    """Chuẩn hóa đáp án đúng: hỗ trợ cả dữ liệu cũ (correctOptionId) lẫn mới."""
    ids = question.get("correctOptionIds")
    if ids is None:
        single = question.get("correctOptionId")
        ids = [single] if single else []
    return [str(item) for item in ids]


def build_assignment_context(
    course: Course,
    module: Module | None,
    lesson: Lesson | None,
    assignment: QuizAssignment,
    attempt: QuizAttempt | None,
    *,
    include_answers: bool,
    draft_answers: dict[str, list[str]] | None = None,
) -> str:
    """Chuỗi ngữ cảnh bài tập gửi kèm.

    `include_answers=False` (hints trước khi nộp) tuyệt đối không chứa đáp án
    đúng/giải thích.
    """
    lines = [
        f"Khóa học: {course.title}",
        f"Chương: {module.title}" if module is not None else "",
        f"Bài học: {lesson.title}" if lesson is not None else "",
        f"Bài tập: {assignment.title}",
        f"Số câu hỏi: {len(assignment.questions)}",
    ]
    lines = [line for line in lines if line]
    if assignment.instructions.strip():
        lines.append(f"Hướng dẫn: {assignment.instructions.strip()}")

    answers = (attempt.answers if attempt is not None else draft_answers) or {}
    for index, question in enumerate(assignment.questions, start=1):
        lines.append(f"Câu {index}: {question['prompt']}")
        for option in question["options"]:
            lines.append(f"- {option['id']}: {option['text']}")
        selected = answers.get(question["id"]) or []
        if isinstance(selected, str):
            selected = [selected]
        lines.append(f"Học viên chọn: {', '.join(selected) if selected else 'chưa trả lời'}")
        if include_answers:
            lines.append(f"Đáp án đúng: {', '.join(question_correct_ids(question))}")
            lines.append(f"Giải thích: {question.get('explanation', '')}")
    context = "\n".join(lines)
    if len(context) > CONTEXT_MAX:
        raise HTTPException(
            422, detail="Ngữ cảnh bài tập vượt giới hạn 30.000 ký tự; cần rút gọn đề để gửi đầy đủ."
        )
    return context


def _title_from(message: str) -> str:
    """Tiêu đề phiên lấy từ câu hỏi đầu tiên (cắt gọn theo từ)."""
    text = " ".join(message.split())
    if len(text) <= TITLE_MAX:
        return text or "Phiên mới"
    return text[: TITLE_MAX - 1].rstrip() + "…"


def _chatbot_ready() -> bool:
    return bool(settings.chatbot_url_resolved and settings.chatbot_internal_token)


def _headers() -> dict[str, str]:
    return {"X-Chatbot-Token": settings.chatbot_internal_token}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _citation_out(citation: dict) -> dict:
    """Chuyển citation snake_case của chatbot sang camelCase cho frontend."""
    return {
        "documentId": citation.get("document_id"),
        "title": citation.get("title") or "",
        "location": citation.get("location") or "",
        "lessonId": citation.get("lesson_id"),
        "lessonTitle": citation.get("lesson_title") or "",
        "slideId": citation.get("slide_id"),
        "slideIndex": citation.get("slide_index"),
        "imageUrl": citation.get("image_url") or "",
        "snippet": citation.get("snippet") or "",
        "score": citation.get("score") or 0.0,
    }


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
    return [{"role": message.role, "content": message.content} for message in reversed(rows)]


def _payload(
    *,
    course: Course,
    session: ChatSession,
    message: str,
    history: list[dict],
    lesson: Lesson | None,
    module: Module | None,
    assignment: QuizAssignment | None,
    attempt: QuizAttempt | None,
    support_mode: str,
    draft_answers: dict[str, list[str]] | None = None,
) -> dict:
    context = ""
    if assignment is not None:
        context = build_assignment_context(
            course,
            module,
            lesson,
            assignment,
            attempt,
            include_answers=support_mode == "review",
            draft_answers=draft_answers,
        )
    return {
        "message": message,
        "course_id": course.id,
        "thread_id": session.id,
        "context_key": session.context_key,
        "history": history,
        "lesson_id": lesson.id if lesson is not None else None,
        "lesson_title": lesson.title if lesson is not None else "",
        "module_title": module.title if module is not None else "",
        "assignment_id": assignment.id if assignment is not None else None,
        "assignment_title": assignment.title if assignment is not None else "",
        "assignment_context": context,
        "support_mode": support_mode,
    }


async def _ask_chatbot(payload: dict) -> dict:
    async with httpx.AsyncClient(
        timeout=settings.chatbot_timeout_seconds,
        headers=_headers(),
    ) as client:
        response = await client.post(
            f"{settings.chatbot_url_resolved.rstrip('/')}/chat", json=payload
        )
        response.raise_for_status()
        return response.json()


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
        # Tiêu đề lấy từ câu hỏi đầu tiên nếu có thể.
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


async def _ensure_access(session: ChatSession) -> None:
    # A separate short transaction sees changes from other tabs.
    async with SessionLocal() as check:
        await ensure_access_in_db(check, session)


async def ensure_access_in_db(check: AsyncSession, session: ChatSession) -> None:
    enrolled = (
        await check.execute(
            select(Enrollment.id)
            .join(Course)
            .where(
                Enrollment.course_id == session.course_id,
                Enrollment.student_id == session.student_id,
                Enrollment.status == "active",
                Course.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if enrolled is None:
        raise HTTPException(403, detail="Khóa học không còn khả dụng")
    await require_chat_access(check, session.course_id, session.student_id)
    if session.assignment_id is None and await active_assignments(
        check, session.course_id, session.student_id
    ):
        raise HTTPException(
            403, detail="Bạn đã bắt đầu bài tập. Vui lòng gửi lại câu hỏi để dùng ngữ cảnh mới."
        )
    key = await context_key(check, session.assignment_id, session.student_id, session.lesson_id)
    if key != session.context_key:
        raise HTTPException(
            403, detail="Ngữ cảnh bài tập đã thay đổi. Vui lòng gửi lại câu hỏi."
        )

async def answer_in_session(
    db: AsyncSession,
    *,
    course: Course,
    session: ChatSession,
    message: str,
    lesson: Lesson | None,
    module: Module | None,
    assignment: QuizAssignment | None,
    attempt: QuizAttempt | None,
    support_mode: str,
    draft_answers: dict[str, list[str]] | None = None,
) -> tuple[str, list[dict], str | None, bool]:
    """Gọi chatbot cho một lượt hỏi rồi lưu cả câu hỏi lẫn câu trả lời."""
    if not _chatbot_ready():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trợ lý học tập chưa được cấu hình",
        )

    history = await _history(db, session.id)
    payload = _payload(
        course=course,
        session=session,
        message=message,
        history=history,
        lesson=lesson,
        module=module,
        assignment=assignment,
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

    try:
        data = await _ask_chatbot(payload)
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="Trợ lý học tập tạm thời không phản hồi",
        ) from exc

    await _ensure_access(session)
    answer = data.get("answer") or ""
    citations = data.get("citations") or []
    intent = data.get("intent")
    verified = bool(data.get("verified", True))

    await _persist_assistant(
        db,
        session=session,
        answer=answer,
        citations=citations,
        intent=intent,
    )
    return answer, citations, intent, verified


async def _guarded_lines(response: httpx.Response, session: ChatSession) -> AsyncIterator[str]:
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


async def stream_in_session(
    db: AsyncSession,
    *,
    course: Course,
    session: ChatSession,
    message: str,
    lesson: Lesson | None,
    module: Module | None,
    assignment: QuizAssignment | None,
    attempt: QuizAttempt | None,
    support_mode: str,
    draft_answers: dict[str, list[str]] | None = None,
) -> AsyncIterator[str]:
    """Proxy SSE từ chatbot, đồng thời lưu assistant message khi nhận `done`."""
    if not _chatbot_ready():
        yield _sse("error", {"message": "Trợ lý học tập chưa được cấu hình"})
        return

    history = await _history(db, session.id)
    payload = _payload(
        course=course,
        session=session,
        message=message,
        history=history,
        lesson=lesson,
        module=module,
        assignment=assignment,
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

    yield _sse("session", {"sessionId": session.id})

    answer_parts: list[str] = []
    citations: list[dict] = []
    intent: str | None = None
    completed = False

    try:
        async with httpx.AsyncClient(
            timeout=settings.chatbot_timeout_seconds,
            headers=_headers(),
        ) as client:
            async with client.stream(
                "POST",
                f"{settings.chatbot_url_resolved.rstrip('/')}/chat/stream",
                json=payload,
            ) as response:
                if response.status_code != 200:
                    await response.aread()
                    yield _sse(
                        "error",
                        {"message": "Trợ lý học tập tạm thời không phản hồi"},
                    )
                    return

                event_name = ""
                data_lines: list[str] = []
                async for line in _guarded_lines(response, session):
                    if line == ": heartbeat":
                        yield ": heartbeat\n\n"
                        continue
                    if line == "":
                        if event_name and data_lines:
                            raw = "\n".join(data_lines)
                            try:
                                data = json.loads(raw)
                            except json.JSONDecodeError:
                                data = {}
                            await _ensure_access(session)
                            if event_name == "token":
                                answer_parts.append(data.get("text") or "")
                                yield _sse("token", data)
                            elif event_name == "citations":
                                citations = [
                                    _citation_out(item) for item in (data.get("citations") or [])
                                ]
                                yield _sse("citations", {**data, "citations": citations})
                            elif event_name == "done":
                                intent = data.get("intent")
                                assistant = await _persist_assistant(
                                    db,
                                    session=session,
                                    answer="".join(answer_parts),
                                    citations=citations,
                                    intent=intent,
                                )
                                completed = True
                                yield _sse(
                                    "done",
                                    {
                                        **data,
                                        "sessionId": session.id,
                                        "messageId": assistant.id,
                                    },
                                )
                            elif event_name == "error":
                                yield _sse("error", data)
                            elif event_name == "status":
                                yield _sse(event_name, data)
                        event_name = ""
                        data_lines = []
                        continue

                    if line.startswith("event:"):
                        event_name = line[len("event:") :].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line[len("data:") :].strip())
    except HTTPException as exc:
        yield _sse("error", {"message": exc.detail, "status": exc.status_code})
    except httpx.HTTPError:
        logger.warning("Chatbot stream lỗi", exc_info=True)
        yield _sse("error", {"message": "Trợ lý học tập tạm thời không phản hồi"})
    finally:
        if not completed:
            logger.info("SSE kết thúc trước khi verify xong — không lưu assistant message")
