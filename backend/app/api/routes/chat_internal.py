"""Internal, fixed read operations. Student and course come only from persisted session."""

import secrets
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.chat import ChatSession
from app.models.course import Course, Lesson, Module
from app.models.quiz import QuizAssignment, QuizAttempt, QuizAttemptSession
from app.services.chat_access import attempt_deadline
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
    operation: Literal["access", "course", "structure", "assignments", "assignment", "results"]
    target: str = Field(default="", max_length=255)


def iso(value):
    return value.isoformat() if value else None


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
    if body.operation == "course":
        title, description = (
            await db.execute(
                select(Course.title, Course.description).where(Course.id == session.course_id)
            )
        ).one()
        return {
            **base,
            "course": {
                "title": title,
                "description": description or "",
                "url": f"/student/courses/{session.course_id}",
            },
        }
    if body.operation == "structure":
        rows = (
            await db.execute(
                select(Module.title, Lesson.id, Lesson.title)
                .outerjoin(Lesson, Lesson.module_id == Module.id)
                .where(Module.course_id == session.course_id)
                .order_by(Module.order_index, Lesson.order_index)
            )
        ).all()
        return {
            **base,
            "lessons": [
                {
                    "module": m,
                    "title": title or "Chưa có bài học",
                    "url": f"/student/courses/{session.course_id}?lesson={lid}" if lid else None,
                }
                for m, lid, title in rows
            ],
        }
    rows = (
        await db.execute(
            select(QuizAssignment, QuizAttempt, QuizAttemptSession.started_at)
            .outerjoin(
                QuizAttempt,
                and_(
                    QuizAttempt.assignment_id == QuizAssignment.id,
                    QuizAttempt.student_id == session.student_id,
                ),
            )
            .outerjoin(
                QuizAttemptSession,
                and_(
                    QuizAttemptSession.assignment_id == QuizAssignment.id,
                    QuizAttemptSession.student_id == session.student_id,
                ),
            )
            .where(QuizAssignment.course_id == session.course_id, QuizAssignment.status != "draft")
            .order_by(QuizAssignment.created_at, QuizAssignment.id)
        )
    ).all()
    if body.operation == "assignment" or (body.operation == "results" and body.target.strip()):
        target = body.target.strip().casefold()
        if target:
            rows = [
                row for row in rows if str(row[0].id) == target or row[0].title.casefold() == target
            ]
        elif session.assignment_id:
            rows = [row for row in rows if row[0].id == session.assignment_id]
        if len(rows) != 1:
            return {
                **base,
                "clarification": "Hãy chọn đúng bài tập (tên hoặc mã bài).",
                "choices": [{"id": a.id, "title": a.title} for a, _, _ in rows],
            }
    result = []
    for assignment, attempt, started in rows:
        deadline = (
            attempt_deadline(assignment.due_at, assignment.duration_minutes, started)
            if started
            else assignment.due_at
        )
        state = (
            "đã nộp"
            if attempt
            else "đang làm"
            if started and deadline and deadline > now
            else "hết giờ"
            if started
            else "quá hạn"
            if deadline and deadline <= now
            else "chưa làm"
        )
        item = {
            "id": assignment.id,
            "title": assignment.title,
            "status": state,
            "due_at": iso(assignment.due_at),
            "attempt_deadline": iso(deadline),
            "remaining_seconds": max(0, int((deadline - now).total_seconds()))
            if deadline and not attempt
            else None,
            "duration_minutes": assignment.duration_minutes,
            "url": f"/student/courses/{session.course_id}?lesson={assignment.lesson_id}"
            if assignment.lesson_id
            else f"/student/courses/{session.course_id}",
        }
        if body.operation == "assignment":
            item["instructions"] = assignment.instructions
        if body.operation == "results":
            # The public attempt endpoint exposes exactly these personal scores after submission.
            item["score"] = attempt.score if attempt else None
            item["max_score"] = attempt.max_score if attempt else None
            item["submitted_at"] = iso(attempt.submitted_at) if attempt else None
        result.append(item)
    return {**base, "assignments": result}
