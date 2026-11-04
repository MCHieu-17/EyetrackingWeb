"""Course-wide quiz restrictions, evaluated from current database rows."""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import QuizAssignment, QuizAttempt, QuizAttemptSession


def attempt_deadline(due_at: datetime | None, duration: int, started_at: datetime) -> datetime:
    deadline = started_at + timedelta(minutes=duration)
    return min(due_at, deadline) if due_at is not None else deadline


async def chat_access(db: AsyncSession, course_id: str, student_id: str) -> dict:
    # Select scalar columns so a long-running request never uses stale ORM state.
    rows = (
        await db.execute(
            select(
                QuizAssignment.due_at,
                QuizAssignment.duration_minutes,
                QuizAttemptSession.started_at,
            )
            .join(QuizAttemptSession, QuizAttemptSession.assignment_id == QuizAssignment.id)
            .outerjoin(
                QuizAttempt,
                and_(
                    QuizAttempt.assignment_id == QuizAssignment.id,
                    QuizAttempt.student_id == QuizAttemptSession.student_id,
                ),
            )
            .where(
                QuizAssignment.course_id == course_id,
                QuizAssignment.allow_chatbot.is_(False),
                QuizAttemptSession.student_id == student_id,
                QuizAttempt.id.is_(None),
            )
        )
    ).all()
    now = datetime.now(timezone.utc)
    deadlines = [attempt_deadline(due, duration, started) for due, duration, started in rows]
    active = [deadline for deadline in deadlines if deadline > now]
    return {
        "allowed": not active,
        "reason": "Chatbot bị khóa trong khóa học đến khi bạn nộp hoặc hết giờ các bài tập không cho phép chatbot."
        if active
        else None,
        "blockedUntil": max(active) if active else None,
    }


async def require_chat_access(db: AsyncSession, course_id: str, student_id: str) -> None:
    access = await chat_access(db, course_id, student_id)
    if not access["allowed"]:
        raise HTTPException(403, detail=access["reason"])


async def context_key(
    db: AsyncSession, assignment_id: str | None, student_id: str, lesson_id: str | None
) -> str:
    if assignment_id is None:
        return "reader:course"
    row = (
        await db.execute(
            select(QuizAssignment.updated_at, QuizAttempt.id, QuizAttemptSession.started_at)
            .outerjoin(
                QuizAttempt,
                and_(
                    QuizAttempt.assignment_id == QuizAssignment.id,
                    QuizAttempt.student_id == student_id,
                ),
            )
            .outerjoin(
                QuizAttemptSession,
                and_(
                    QuizAttemptSession.assignment_id == QuizAssignment.id,
                    QuizAttemptSession.student_id == student_id,
                ),
            )
            .where(QuizAssignment.id == assignment_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(403, detail="Ngữ cảnh bài tập không còn khả dụng")
    updated, attempt_id, started = row
    return f"{assignment_id}:{updated.isoformat()}:{attempt_id or 'hint'}:{started.isoformat() if started else ''}"


async def active_assignments(db: AsyncSession, course_id: str, student_id: str) -> list[str]:
    rows = (
        await db.execute(
            select(
                QuizAssignment.id,
                QuizAssignment.due_at,
                QuizAssignment.duration_minutes,
                QuizAttemptSession.started_at,
            )
            .join(QuizAttemptSession, QuizAttemptSession.assignment_id == QuizAssignment.id)
            .outerjoin(
                QuizAttempt,
                and_(
                    QuizAttempt.assignment_id == QuizAssignment.id,
                    QuizAttempt.student_id == QuizAttemptSession.student_id,
                ),
            )
            .where(
                QuizAssignment.course_id == course_id,
                QuizAttemptSession.student_id == student_id,
                QuizAttempt.id.is_(None),
            )
            .order_by(QuizAttemptSession.started_at.desc())
        )
    ).all()
    now = datetime.now(timezone.utc)
    return [
        assignment_id
        for assignment_id, due, duration, started in rows
        if attempt_deadline(due, duration, started) > now
    ]
