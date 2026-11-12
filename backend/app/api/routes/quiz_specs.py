from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload

from app.api.access import get_course_or_404
from app.api.deps import can_manage_course, require_roles
from app.db.session import get_db
from app.models.auth import User
from app.models.course import Course, CourseVersionItem, Lesson, LessonVersion
from app.models.quiz import QuizSpec
from app.schemas.quiz import QuizAssignmentOut, QuizAssignmentUpdate
from app.services import content

router = APIRouter(tags=["quiz-specs"])


async def _sync_published_quiz_flags(
    db: AsyncSession,
    course: Course,
    lesson_id: str,
    *,
    allow_retry: bool | None,
    allow_chatbot: bool | None,
) -> None:
    """Đồng bộ cờ vận hành sang QuizSpec của bản xuất bản.

    `allow_retry`/`allow_chatbot` là thiết lập runtime, không phải nội dung.
    Giáo viên bật/tắt phải có hiệu lực ngay với sinh viên mà không cần publish
    lại toàn bộ khóa học.
    """
    if course.published_version_id is None:
        return
    published_item = (
        await db.execute(
            select(CourseVersionItem).where(
                CourseVersionItem.course_version_id == course.published_version_id,
                CourseVersionItem.lesson_id == lesson_id,
            )
        )
    ).scalar_one_or_none()
    if published_item is None:
        return
    published_quiz = await db.get(QuizSpec, published_item.lesson_version_id)
    if published_quiz is None:
        return
    if allow_retry is not None:
        published_quiz.allow_retry = allow_retry
    if allow_chatbot is not None:
        published_quiz.allow_chatbot = allow_chatbot


@router.patch(
    "/teacher/quiz-specs/{lesson_version_id}",
    response_model=QuizAssignmentOut,
)
async def update_quiz_spec(
    lesson_version_id: str,
    body: QuizAssignmentUpdate,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    lesson_version = await db.get(
        LessonVersion,
        lesson_version_id,
        options=[raiseload(LessonVersion.slides)],
    )
    if lesson_version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài tập")
    lesson = await db.get(
        Lesson,
        lesson_version.lesson_id,
        options=[raiseload(Lesson.versions), raiseload(Lesson.slides)],
    )
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    course = await get_course_or_404(db, lesson.course_id)
    if not await can_manage_course(db, course, user):
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
    if body.status == "published":
        # "Giao bài cho học viên" phải đưa bài tập vào bản xuất bản để sinh
        # viên thấy. Bản xuất bản là bất biến nên cách duy nhất là xuất bản
        # course version nháp hiện tại (kéo theo các thay đổi nháp khác).
        await content.publish_course(db, course, user, None)
    else:
        # Cờ làm lại/chatbot phải có hiệu lực với sinh viên ngay, kể cả khi
        # giáo viên chưa publish lại nội dung. Chỉ chạy khi có đổi cờ để
        # không thêm query cho các lần lưu nội dung thông thường.
        allow_retry = data.get("allow_retry")
        allow_chatbot = data.get("allow_chatbot")
        if allow_retry is not None or allow_chatbot is not None:
            await _sync_published_quiz_flags(
                db,
                course,
                lesson.id,
                allow_retry=allow_retry,
                allow_chatbot=allow_chatbot,
            )
    await db.commit()
    await db.refresh(quiz)
    await db.refresh(draft_lesson_version)

    published_quiz_lessons = await content.published_quiz_lesson_ids(db, course)
    effective_status = (
        "published" if lesson.id in published_quiz_lessons else "draft"
    )

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
        status=effective_status,
        created_at=draft_lesson_version.created_at,
        allow_chatbot=quiz.allow_chatbot,
        allow_retry=quiz.allow_retry,
        questions=quiz.questions,
    )
