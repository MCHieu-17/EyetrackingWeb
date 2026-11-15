"""Course-wide quiz restrictions for the study chatbot."""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import CourseModule, Enrollment, Lesson
from app.models.quiz import QuizAttempt


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _allow_chatbot(lesson: Lesson | None) -> bool:
    if lesson is None:
        return True
    config = lesson.quiz_config or {}
    return bool(config.get("allowChatbot"))


async def chat_access(db: AsyncSession, course_id: str, student_id: str) -> dict:
    rows = (
        await db.execute(
            select(QuizAttempt.expires_at, Lesson)
            .join(Lesson, Lesson.id == QuizAttempt.lesson_id)
            .join(CourseModule, CourseModule.id == Lesson.module_id)
            .join(Enrollment, Enrollment.id == QuizAttempt.enrollment_id)
            .where(
                CourseModule.course_id == course_id,
                Enrollment.student_id == student_id,
                QuizAttempt.status == "in_progress",
                QuizAttempt.expires_at > _now(),
            )
        )
    ).all()
    active = [
        deadline
        for deadline, lesson in rows
        if not _allow_chatbot(lesson) and deadline is not None
    ]
    return {
        "allowed": not active,
        "reason": (
            "Chatbot bị khóa trong khóa học đến khi bạn nộp hoặc hết giờ các bài tập "
            "không cho phép chatbot."
            if active
            else None
        ),
        "blockedUntil": max(active) if active else None,
    }


async def require_chat_access(db: AsyncSession, course_id: str, student_id: str) -> None:
    access = await chat_access(db, course_id, student_id)
    if not access["allowed"]:
        raise HTTPException(403, detail=access["reason"])


async def active_attempts(
    db: AsyncSession, course_id: str, student_id: str
) -> list[dict]:
    rows = (
        await db.execute(
            select(
                QuizAttempt.id,
                QuizAttempt.lesson_id,
                QuizAttempt.expires_at,
            )
            .join(Lesson, Lesson.id == QuizAttempt.lesson_id)
            .join(CourseModule, CourseModule.id == Lesson.module_id)
            .join(Enrollment, Enrollment.id == QuizAttempt.enrollment_id)
            .where(
                CourseModule.course_id == course_id,
                Enrollment.student_id == student_id,
                QuizAttempt.status == "in_progress",
                QuizAttempt.expires_at > _now(),
            )
            .order_by(QuizAttempt.started_at.desc())
        )
    ).all()
    return [
        {
            "attemptId": attempt_id,
            "lessonId": lesson_id,
            "expiresAt": expires_at,
        }
        for attempt_id, lesson_id, expires_at in rows
    ]


def context_key(
    *,
    lesson_id: str | None,
    attempt_id: str | None,
    attempt_status: str | None,
) -> str:
    return (
        f"lesson:{lesson_id or ''}:"
        f"attempt:{attempt_id or 'none'}:{attempt_status or ''}"
    )
