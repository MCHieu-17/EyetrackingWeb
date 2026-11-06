from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import can_access_course, require_roles
from app.db.session import get_db
from app.models.auth import User
from app.models.course import Course, Lesson, LessonVersion
from app.models.quiz import QuizSpec
from app.schemas.quiz import QuizAssignmentOut, QuizAssignmentUpdate
from app.services import content

router = APIRouter(tags=["quiz-specs"])


@router.patch(
    "/api/teacher/quiz-specs/{lesson_version_id}",
    response_model=QuizAssignmentOut,
)
async def update_quiz_spec(
    lesson_version_id: str,
    body: QuizAssignmentUpdate,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    lesson_version = await db.get(LessonVersion, lesson_version_id)
    if lesson_version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài tập")
    lesson = await db.get(Lesson, lesson_version.lesson_id)
    course = await db.get(Course, lesson.course_id) if lesson else None
    if lesson is None or course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    if not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")

    draft, item = await content.get_draft_item_for_lesson(
        db, course, lesson.id, user
    )
    draft_lesson_version = await content.ensure_draft_lesson_version(db, item, user)
    quiz = await db.get(QuizSpec, draft_lesson_version.id)
    if quiz is None:
        quiz = QuizSpec(
            lesson_version_id=draft_lesson_version.id,
            instructions="",
            duration_minutes=body.duration_minutes or 15,
            questions=[],
        )
        db.add(quiz)
        await db.flush()

    data = body.model_dump(exclude_unset=True)
    if data.get("title") is not None:
        draft_lesson_version.title = data["title"].strip()
    if data.get("instructions") is not None:
        quiz.instructions = data["instructions"].strip()
    if "due_at" in data:
        quiz.due_at = data["due_at"]
    if data.get("duration_minutes") is not None:
        quiz.duration_minutes = data["duration_minutes"]
    if data.get("allow_chatbot") is not None:
        quiz.allow_chatbot = data["allow_chatbot"]
    if data.get("allow_retry") is not None:
        quiz.allow_retry = data["allow_retry"]
    if body.questions is not None:
        quiz.questions = [
            question.model_dump(by_alias=True) for question in body.questions
        ]
    content.bump_generation(draft)
    await db.commit()
    await db.refresh(quiz)
    await db.refresh(draft_lesson_version)

    return QuizAssignmentOut(
        id=draft_lesson_version.id,
        course_id=course.id,
        course_title=draft.title,
        lesson_id=lesson.id,
        lesson_title=draft_lesson_version.title,
        title=draft_lesson_version.title,
        instructions=quiz.instructions,
        due_at=quiz.due_at,
        duration_minutes=quiz.duration_minutes,
        status="draft" if draft_lesson_version.state == "draft" else "published",
        created_at=draft_lesson_version.created_at,
        allow_chatbot=quiz.allow_chatbot,
        allow_retry=quiz.allow_retry,
        questions=quiz.questions,
    )
