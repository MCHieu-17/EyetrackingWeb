"""Internal, fixed read operations for the chatbot."""

import secrets
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.chat import ChatSession
from app.models.course import Course, CourseModule, Enrollment, Lesson
from app.models.quiz import QuizAttempt
from app.services.study_chat import ensure_access_in_db

router = APIRouter(tags=["internal-chat"])


def internal_auth(x_chatbot_token: str = Header(default="")):
    if not settings.chatbot_internal_token or not secrets.compare_digest(
        x_chatbot_token, settings.chatbot_internal_token
    ):
        raise HTTPException(401, detail="Unauthorized")


class LMSQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID
    context_key: str = Field(max_length=512)
    operation: Literal[
        "access", "course", "structure", "assignments", "assignment", "results"
    ]
    target: str = Field(default="", max_length=255)


def iso(value):
    return value.isoformat() if value else None


def _attempt_state(attempt: QuizAttempt | None, now: datetime) -> str:
    if attempt is None:
        return "chưa làm"
    if attempt.status == "submitted":
        return "đã nộp"
    if attempt.status == "expired" or attempt.expires_at <= now:
        return "hết giờ"
    return "đang làm"


@router.post("/internal/chat/lms-query", dependencies=[Depends(internal_auth)])
async def query_lms(body: LMSQuery, db: AsyncSession = Depends(get_db)):
    session = await db.get(ChatSession, str(body.session_id))
    if session is None or session.archived_at is not None:
        raise HTTPException(404, detail="Phiên chat không còn khả dụng")
    if session.context_key != body.context_key:
        raise HTTPException(403, detail="Ngữ cảnh đã thay đổi")
    await ensure_access_in_db(db, session)

    now = datetime.now(timezone.utc)
    base = {"course_id": session.course_id, "server_now": iso(now)}
    if body.operation == "access":
        return {**base, "allowed": True}

    course = await db.get(Course, session.course_id)
    if course is None or course.status != "published":
        raise HTTPException(404, detail="Khóa học không còn khả dụng")

    if body.operation == "course":
        return {
            **base,
            "course": {
                "title": course.title,
                "description": course.description or "",
                "url": f"/student/courses/{session.course_id}",
            },
        }

    modules = (
        await db.execute(
            select(CourseModule)
            .where(CourseModule.course_id == course.id)
            .order_by(CourseModule.position)
        )
    ).scalars().all()
    lessons = (
        await db.execute(
            select(Lesson)
            .where(Lesson.module_id.in_([module.id for module in modules]))
            .order_by(Lesson.position)
        )
    ).scalars().all()
    module_titles = {module.id: module.title for module in modules}

    if body.operation == "structure":
        return {
            **base,
            "lessons": [
                {
                    "module": module_titles.get(lesson.module_id, ""),
                    "title": lesson.title,
                    "url": (
                        f"/student/courses/{session.course_id}?lesson={lesson.id}"
                    ),
                }
                for lesson in lessons
            ],
        }

    quiz_lessons = [lesson for lesson in lessons if lesson.kind == "quiz"]
    if body.operation in {"assignment", "results"}:
        target = body.target.strip().casefold()
        if target:
            quiz_lessons = [
                lesson
                for lesson in quiz_lessons
                if lesson.id == target or lesson.title.casefold() == target
            ]
        elif session.lesson_id:
            quiz_lessons = [
                lesson for lesson in quiz_lessons if lesson.id == session.lesson_id
            ]
        if len(quiz_lessons) != 1:
            return {
                **base,
                "clarification": "Hãy chọn đúng bài tập (tên hoặc mã bài).",
                "choices": [
                    {"id": lesson.id, "title": lesson.title}
                    for lesson in quiz_lessons
                ],
            }

    enrollment_ids = list(
        (
            await db.execute(
                select(Enrollment.id).where(
                    Enrollment.course_id == course.id,
                    Enrollment.student_id == session.student_id,
                )
            )
        ).scalars()
    )
    attempts = (
        await db.execute(
            select(QuizAttempt)
            .where(QuizAttempt.enrollment_id.in_(enrollment_ids))
            .order_by(QuizAttempt.attempt_no.desc())
        )
    ).scalars().all()
    latest: dict[str, QuizAttempt] = {}
    for attempt in attempts:
        latest.setdefault(attempt.lesson_id, attempt)

    result = []
    for lesson in quiz_lessons:
        config = lesson.quiz_config or {}
        attempt = latest.get(lesson.id)
        if body.operation == "results" and session.quiz_attempt_id:
            session_attempt = await db.get(QuizAttempt, session.quiz_attempt_id)
            if session_attempt is not None and session_attempt.lesson_id == lesson.id:
                attempt = session_attempt
        state = _attempt_state(attempt, now)
        due_at = config.get("dueAt")
        deadline_raw = attempt.expires_at if attempt else due_at
        if isinstance(deadline_raw, str):
            try:
                deadline = datetime.fromisoformat(
                    deadline_raw.replace("Z", "+00:00")
                )
            except ValueError:
                deadline = None
        else:
            deadline = deadline_raw
        entry = {
            "id": lesson.id,
            "lesson_id": lesson.id,
            "title": lesson.title,
            "status": state,
            "due_at": iso(deadline) if due_at else None,
            "attempt_deadline": iso(deadline),
            "remaining_seconds": (
                max(0, int((deadline - now).total_seconds()))
                if deadline and attempt and attempt.status == "in_progress"
                else None
            ),
            "duration_minutes": config.get("durationMinutes", 15),
            "url": f"/student/courses/{session.course_id}?lesson={lesson.id}",
        }
        if body.operation == "assignment":
            entry["instructions"] = config.get("instructions", "")
        if body.operation == "results":
            entry["attempt_id"] = attempt.id if attempt else None
            entry["score"] = attempt.score if attempt else None
            entry["max_score"] = attempt.max_score if attempt else None
            entry["submitted_at"] = iso(attempt.submitted_at) if attempt else None
        result.append(entry)
    return {**base, "assignments": result}
