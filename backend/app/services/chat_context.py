"""Context và lifecycle cho chat học tập.

Tách khỏi HTTP route: xác định enrollment, lesson/quiz, attempt hiện hành và
session chat tương ứng. Route chỉ xử lý request/response/SSE.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.chat import ChatMessage, ChatSession
from app.models.course import Course, CourseModule, Enrollment, Lesson
from app.models.quiz import QuizAttempt
from app.schemas.chat import ChatSendIn, ChatSessionOut
from app.services.access import validate_uuid
from app.services.chat_access import active_attempts, context_key

NEW_TITLE = "Phiên mới"

async def _require_enrolled(db: AsyncSession, course_id: str, user: User) -> None:
    stmt = select(Enrollment.id).where(
        Enrollment.course_id == course_id,
        Enrollment.student_id == user.id,
        Enrollment.status == "active",
    )
    if (await db.execute(stmt)).scalar_one_or_none() is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Bạn chưa tham gia khóa học"
        )


async def _session_or_404(
    db: AsyncSession, session_id: str, user: User
) -> ChatSession:
    validate_uuid(session_id, "Không tìm thấy phiên chat")
    session = await db.get(ChatSession, session_id)
    if (
        session is None
        or session.student_id != user.id
        or session.archived_at is not None
    ):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên chat"
        )
    return session


async def _message_count(db: AsyncSession, session_id: str) -> int:
    return int(
        (
            await db.execute(
                select(func.count(ChatMessage.id)).where(
                    ChatMessage.session_id == session_id
                )
            )
        ).scalar_one()
    )


def _session_out(session: ChatSession, count: int = 0) -> ChatSessionOut:
    return ChatSessionOut(
        id=session.id,
        course_id=session.course_id,
        lesson_id=session.lesson_id,
        assignment_id=session.lesson_id,
        attempt_id=session.quiz_attempt_id,
        title=session.title,
        message_count=count,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


async def _latest_attempt(
    db: AsyncSession, enrollment_id: str, lesson_id: str
) -> QuizAttempt | None:
    return (
        await db.execute(
            select(QuizAttempt)
            .where(
                QuizAttempt.enrollment_id == enrollment_id,
                QuizAttempt.lesson_id == lesson_id,
            )
            .order_by(QuizAttempt.attempt_no.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _resolve_context(
    db: AsyncSession,
    course: Course,
    body: ChatSendIn,
    user: User,
) -> tuple[Lesson | None, str | None, dict | None, QuizAttempt | None, str, str]:
    if course.status != "published":
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Khóa học chưa được xuất bản"
        )
    enrollment = (
        await db.execute(
            select(Enrollment).where(
                Enrollment.course_id == course.id,
                Enrollment.student_id == user.id,
                Enrollment.status == "active",
            )
        )
    ).scalar_one_or_none()
    if enrollment is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Bạn chưa tham gia khóa học"
        )

    lesson: Lesson | None = None
    attempt: QuizAttempt | None = None
    if body.attempt_id is not None:
        attempt = await db.get(QuizAttempt, str(body.attempt_id))
        if attempt is None or attempt.enrollment_id != enrollment.id:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lượt làm bài"
            )
        lesson = await db.get(Lesson, attempt.lesson_id)
        if lesson is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài tập"
            )
        if body.assignment_id is not None and str(body.assignment_id) != lesson.id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Lượt làm bài không khớp bài tập đã chọn",
            )
    elif body.assignment_id is not None:
        lesson = await db.get(Lesson, str(body.assignment_id))
        if lesson is None or lesson.kind != "quiz":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Bài tập không thuộc khóa học"
            )
        attempt = await _latest_attempt(db, enrollment.id, lesson.id)
        if attempt is not None and (
            attempt.status == "expired"
            or (
                attempt.status == "in_progress"
                and attempt.expires_at <= datetime.now(timezone.utc)
            )
        ):
            attempt = None
    elif body.lesson_id is not None:
        lesson = await db.get(Lesson, str(body.lesson_id))
    else:
        active = await active_attempts(db, course.id, user.id)
        if len(active) > 1:
            raise HTTPException(
                400,
                detail="Bạn đang làm nhiều bài tập. Hãy chọn bài cần gợi ý.",
            )
        if len(active) == 1:
            attempt = await db.get(QuizAttempt, active[0]["attemptId"])
            if attempt is not None:
                lesson = await db.get(Lesson, attempt.lesson_id)

    module_title = None
    quiz: dict | None = None
    if lesson is not None:
        module = await db.get(CourseModule, lesson.module_id)
        if module is None or module.course_id != course.id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Bài học không thuộc khóa học"
            )
        module_title = module.title
        if lesson.kind == "quiz":
            quiz = dict(lesson.quiz_config or {})

    support_mode = (
        "review"
        if attempt is not None and attempt.status == "submitted"
        else "hint"
    )
    if body.draft_answers:
        if quiz is None:
            raise HTTPException(400, detail="Lựa chọn tạm cần có bài tập")
        valid = {
            question["id"]: {option["id"] for option in question["options"]}
            for question in (quiz.get("questions") or [])
        }
        for question_id, options in body.draft_answers.items():
            if question_id not in valid or any(
                option not in valid[question_id] for option in options
            ):
                raise HTTPException(
                    400, detail="Câu hỏi hoặc lựa chọn không thuộc bài tập"
                )

    key = context_key(
        lesson_id=lesson.id if lesson else None,
        attempt_id=attempt.id if attempt else None,
        attempt_status=attempt.status if attempt else None,
    )
    return lesson, module_title, quiz, attempt, support_mode, key


async def _prepare(
    db: AsyncSession,
    course: Course,
    body: ChatSendIn,
    user: User,
) -> tuple[ChatSession, Lesson | None, str | None, dict | None, QuizAttempt | None, str]:
    lesson, module_title, quiz, attempt, support_mode, key = await _resolve_context(
        db, course, body, user
    )
    session = None
    if body.session_id is not None:
        session = await _session_or_404(db, str(body.session_id), user)
        if session.course_id != course.id or session.context_key != key:
            session = None
    if session is None:
        session = ChatSession(
            student_id=user.id,
            course_id=course.id,
            lesson_id=lesson.id if lesson is not None else None,
            quiz_attempt_id=attempt.id if attempt is not None else None,
            title=NEW_TITLE,
            context_key=key,
        )
        db.add(session)
        await db.flush()
    return session, lesson, module_title, quiz, attempt, support_mode
