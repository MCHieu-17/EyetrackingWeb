"""Chuẩn bị payload/history cho chatbot học tập."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession
from app.models.course import Course, Lesson
from app.models.quiz import QuizAttempt

TITLE_MAX = 60
CONTEXT_MAX = 30000
HISTORY_LIMIT = 10


@dataclass(frozen=True)
class ChatSessionSnapshot:
    id: str
    student_id: str
    course_id: str
    lesson_id: str | None
    quiz_attempt_id: str | None
    context_key: str


def snapshot_session(session: ChatSession) -> ChatSessionSnapshot:
    return ChatSessionSnapshot(
        id=session.id,
        student_id=session.student_id,
        course_id=session.course_id,
        lesson_id=session.lesson_id,
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
    quiz: dict,
    attempt: QuizAttempt | None,
    include_answers: bool,
    draft_answers: dict[str, list[str]] | None = None,
) -> str:
    questions = quiz.get("questions") or []
    lines = [
        f"Khóa học: {course_title}",
        f"Chương: {module_title}" if module_title else "",
        f"Bài học: {lesson_title}" if lesson_title else "",
        f"Bài tập: {lesson_title or ''}",
        f"Số câu hỏi: {len(questions)}",
    ]
    lines = [line for line in lines if line]
    instructions = str(quiz.get("instructions") or "").strip()
    if instructions:
        lines.append(f"Hướng dẫn: {instructions}")

    answers = (attempt.answers if attempt is not None else draft_answers) or {}
    for index, question in enumerate(questions, start=1):
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


def title_from(message: str) -> str:
    text = " ".join(message.split())
    if len(text) <= TITLE_MAX:
        return text or "Phiên mới"
    return text[: TITLE_MAX - 1].rstrip() + "…"


async def history(db: AsyncSession, session_id: str) -> list[dict]:
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


def payload(
    *,
    course: Course,
    session: ChatSession,
    message: str,
    history_messages: list[dict],
    lesson: Lesson | None,
    module_title: str | None,
    quiz: dict | None,
    attempt: QuizAttempt | None,
    support_mode: str,
    draft_answers: dict[str, list[str]] | None = None,
) -> dict:
    context = ""
    if quiz is not None and lesson is not None:
        context = build_assignment_context(
            course_title=course.title,
            module_title=module_title,
            lesson_title=lesson.title,
            quiz=quiz,
            attempt=attempt,
            include_answers=support_mode == "review",
            draft_answers=draft_answers,
        )
    return {
        "message": message,
        "course_id": course.id,
        "thread_id": session.id,
        "context_key": session.context_key,
        "history": history_messages,
        "lesson_id": lesson.id if lesson is not None else None,
        "lesson_title": lesson.title if lesson else "",
        "module_title": module_title or "",
        "attempt_id": attempt.id if attempt is not None else None,
        "assignment_id": (
            lesson.id if quiz is not None and lesson is not None else None
        ),
        "assignment_title": lesson.title if lesson else "",
        "assignment_context": context,
        "support_mode": support_mode,
    }
