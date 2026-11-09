"""Internal, fixed read operations for the chatbot.

Student and course come only from the persisted chat session. Every query is
scoped to the session's published course version and, for quiz operations, to a
specific attempt.
"""

import secrets
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload

from app.core.config import settings
from app.db.session import get_db
from app.models.chat import ChatSession
from app.models.course import (
    Course,
    CourseVersion,
    CourseVersionItem,
    CourseVersionModule,
    Enrollment,
    Lesson,
    LessonVersion,
)
from app.models.quiz import QuizAttempt, QuizSpec
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
    session = await db.get(
        ChatSession,
        str(body.session_id),
        options=[raiseload(ChatSession.messages)],
    )
    if session is None or session.archived_at is not None:
        raise HTTPException(404, detail="Phiên chat không còn khả dụng")
    if session.context_key != body.context_key:
        raise HTTPException(403, detail="Ngữ cảnh đã thay đổi")
    await ensure_access_in_db(db, session)

    now = datetime.now(timezone.utc)
    base = {"course_id": session.course_id, "server_now": iso(now)}
    if body.operation == "access":
        return {**base, "allowed": True}

    course = await db.get(
        Course,
        session.course_id,
        options=[
            raiseload(Course.versions),
            raiseload(Course.enrollments),
            raiseload(Course.owner),
            raiseload(Course.creator),
        ],
    )
    version = (
        await db.get(
            CourseVersion,
            session.course_version_id,
            options=[
                raiseload(CourseVersion.modules),
                raiseload(CourseVersion.items),
            ],
        )
        if session.course_version_id
        else None
    )
    if course is None or version is None:
        raise HTTPException(404, detail="Khóa học không còn khả dụng")

    if body.operation == "course":
        return {
            **base,
            "course": {
                "title": version.title,
                "description": version.description or "",
                "url": f"/student/courses/{session.course_id}",
            },
        }

    if body.operation == "structure":
        rows = (
            await db.execute(
                select(
                    CourseVersionModule.title,
                    Lesson.id,
                    LessonVersion.title,
                )
                .join(
                    CourseVersionItem,
                    CourseVersionItem.module_id == CourseVersionModule.id,
                )
                .join(Lesson, Lesson.id == CourseVersionItem.lesson_id)
                .join(
                    LessonVersion,
                    LessonVersion.id == CourseVersionItem.lesson_version_id,
                )
                .where(CourseVersionModule.course_version_id == version.id)
                .order_by(
                    CourseVersionModule.position, CourseVersionItem.position
                )
            )
        ).all()
        return {
            **base,
            "lessons": [
                {
                    "module": module_title,
                    "title": lesson_title,
                    "url": (
                        f"/student/courses/{session.course_id}?lesson={lesson_id}"
                        if lesson_id
                        else None
                    ),
                }
                for module_title, lesson_id, lesson_title in rows
            ],
        }

    quiz_rows = (
        await db.execute(
            select(
                CourseVersionItem,
                Lesson,
                LessonVersion,
                QuizSpec,
            )
            .join(Lesson, Lesson.id == CourseVersionItem.lesson_id)
            .join(
                LessonVersion,
                LessonVersion.id == CourseVersionItem.lesson_version_id,
            )
            .join(QuizSpec, QuizSpec.lesson_version_id == LessonVersion.id)
            .where(
                CourseVersionItem.course_version_id == version.id,
                Lesson.kind == "quiz",
            )
            .order_by(CourseVersionItem.position)
            .options(
                raiseload(Lesson.versions),
                raiseload(Lesson.slides),
                raiseload(LessonVersion.slides),
            )
        )
    ).all()

    attempts = (
        await db.execute(
            select(QuizAttempt)
            .join(
                CourseVersionItem,
                CourseVersionItem.id == QuizAttempt.course_version_item_id,
            )
            .join(Enrollment, Enrollment.id == QuizAttempt.enrollment_id)
            .where(
                CourseVersionItem.course_version_id == version.id,
                Enrollment.course_id == session.course_id,
                Enrollment.student_id == session.student_id,
            )
            .order_by(QuizAttempt.attempt_no.desc())
        )
    ).scalars().all()
    latest: dict[str, QuizAttempt] = {}
    for attempt in attempts:
        latest.setdefault(attempt.lesson_id, attempt)

    if body.operation in {"assignment", "results"}:
        target = body.target.strip().casefold()
        if target:
            quiz_rows = [
                row
                for row in quiz_rows
                if str(row[2].id) == target
                or row[2].title.casefold() == target
                or str(row[0].lesson_id) == target
            ]
        elif session.lesson_version_id:
            quiz_rows = [
                row for row in quiz_rows if row[2].id == session.lesson_version_id
            ]
        if len(quiz_rows) != 1:
            return {
                **base,
                "clarification": "Hãy chọn đúng bài tập (tên hoặc mã bài).",
                "choices": [
                    {"id": row[2].id, "title": row[2].title}
                    for row in quiz_rows
                ],
            }

    result = []
    for item, lesson, lesson_version, quiz in quiz_rows:
        attempt = latest.get(lesson.id)
        if body.operation == "results" and session.quiz_attempt_id:
            session_attempt = await db.get(QuizAttempt, session.quiz_attempt_id)
            if session_attempt is not None and session_attempt.lesson_id == lesson.id:
                attempt = session_attempt
        state = _attempt_state(attempt, now)
        deadline = attempt.expires_at if attempt else quiz.due_at
        entry = {
            "id": lesson_version.id,
            "lesson_id": lesson.id,
            "title": lesson_version.title,
            "status": state,
            "due_at": iso(quiz.due_at),
            "attempt_deadline": iso(deadline),
            "remaining_seconds": (
                max(0, int((deadline - now).total_seconds()))
                if deadline and attempt and attempt.status == "in_progress"
                else None
            ),
            "duration_minutes": quiz.duration_minutes,
            "url": f"/student/courses/{session.course_id}?lesson={lesson.id}",
        }
        if body.operation == "assignment":
            entry["instructions"] = quiz.instructions
        if body.operation == "results":
            entry["attempt_id"] = attempt.id if attempt else None
            entry["score"] = attempt.score if attempt else None
            entry["max_score"] = attempt.max_score if attempt else None
            entry["submitted_at"] = iso(attempt.submitted_at) if attempt else None
        result.append(entry)
    return {**base, "assignments": result}
