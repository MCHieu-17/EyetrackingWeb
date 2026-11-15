from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.access import course_of_lesson
from app.api.deps import can_manage_course, require_roles
from app.db.session import get_db
from app.models.auth import User
from app.models.course import Lesson
from app.schemas.quiz import QuizAssignmentOut, QuizAssignmentUpdate
from app.services import content
from app.services.quiz import parse_datetime

router = APIRouter(tags=["quiz-editor"])


@router.patch(
    "/teacher/lessons/{lesson_id}/quiz",
    response_model=QuizAssignmentOut,
)
async def update_quiz_spec(
    lesson_id: str,
    body: QuizAssignmentUpdate,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None or lesson.kind != "quiz":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài tập")
    course = await course_of_lesson(db, lesson)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    if not await can_manage_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")

    config = dict(lesson.quiz_config or {})
    data = body.model_dump(exclude_unset=True)
    if data.get("title") is not None:
        lesson.title = data["title"].strip()
    if data.get("instructions") is not None:
        config["instructions"] = data["instructions"].strip()
    if "due_at" in data:
        config["dueAt"] = (
            data["due_at"].isoformat() if data["due_at"] is not None else None
        )
    if data.get("duration_minutes") is not None:
        config["durationMinutes"] = data["duration_minutes"]
    if data.get("allow_chatbot") is not None:
        config["allowChatbot"] = data["allow_chatbot"]
    if data.get("allow_retry") is not None:
        config["allowRetry"] = data["allow_retry"]
    if body.questions is not None:
        config["questions"] = [
            question.model_dump(by_alias=True) for question in body.questions
        ]
    if body.status is not None:
        config["status"] = "published" if body.status == "published" else "draft"
    lesson.quiz_config = config
    lesson.updated_at = datetime.now(timezone.utc)

    if body.status == "published":
        await content.publish_course(db, course, user)
    await db.commit()
    await db.refresh(lesson)

    return QuizAssignmentOut(
        id=lesson.id,
        course_id=course.id,
        course_title=course.title,
        lesson_id=lesson.id,
        lesson_title=lesson.title,
        title=lesson.title,
        instructions=str(config.get("instructions") or ""),
        due_at=parse_datetime(config.get("dueAt")),
        duration_minutes=int(config.get("durationMinutes") or 15),
        status=str(config.get("status") or "draft"),
        created_at=lesson.created_at,
        allow_chatbot=bool(config.get("allowChatbot")),
        allow_retry=bool(config.get("allowRetry")),
        questions=list(config.get("questions") or []),
    )
