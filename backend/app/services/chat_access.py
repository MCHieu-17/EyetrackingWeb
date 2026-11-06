"""Course-wide quiz restrictions, evaluated from versioned quiz attempts."""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import CourseVersion, CourseVersionItem, Enrollment
from app.models.quiz import QuizAttempt, QuizSpec


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def chat_access(db: AsyncSession, course_id: str, student_id: str) -> dict:
    rows = (
        await db.execute(
            select(QuizAttempt.expires_at)
            .join(
                CourseVersionItem,
                CourseVersionItem.id == QuizAttempt.course_version_item_id,
            )
            .join(
                CourseVersion,
                CourseVersion.id == CourseVersionItem.course_version_id,
            )
            .join(
                QuizSpec,
                QuizSpec.lesson_version_id == CourseVersionItem.lesson_version_id,
            )
            .join(Enrollment, Enrollment.id == QuizAttempt.enrollment_id)
            .where(
                CourseVersion.course_id == course_id,
                Enrollment.student_id == student_id,
                QuizAttempt.status == "in_progress",
                QuizSpec.allow_chatbot.is_(False),
                QuizAttempt.expires_at > _now(),
            )
        )
    ).scalars().all()
    active = [deadline for deadline in rows if deadline is not None]
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
                CourseVersionItem.lesson_version_id,
                QuizAttempt.expires_at,
            )
            .join(
                CourseVersionItem,
                CourseVersionItem.id == QuizAttempt.course_version_item_id,
            )
            .join(
                CourseVersion,
                CourseVersion.id == CourseVersionItem.course_version_id,
            )
            .join(Enrollment, Enrollment.id == QuizAttempt.enrollment_id)
            .where(
                CourseVersion.course_id == course_id,
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
            "lessonVersionId": lesson_version_id,
            "expiresAt": expires_at,
        }
        for attempt_id, lesson_id, lesson_version_id, expires_at in rows
    ]


def context_key(
    *,
    course_version_id: str | None,
    lesson_version_id: str | None,
    attempt_id: str | None,
    attempt_status: str | None,
) -> str:
    return (
        f"cv:{course_version_id or ''}:"
        f"lv:{lesson_version_id or ''}:"
        f"attempt:{attempt_id or 'none'}:{attempt_status or ''}"
    )
