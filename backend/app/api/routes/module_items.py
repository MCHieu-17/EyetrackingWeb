from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.auth import User
from app.models.course import CourseVersionItem
from app.schemas.course import LessonNodeOut, ModuleItemsReorderIn
from app.schemas.quiz import QuizItemCreate
from app.services import content

router = APIRouter(tags=["module-items"])


@router.post(
    "/teacher/modules/{module_id}/quizzes",
    response_model=LessonNodeOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_quiz_item(
    module_id: str,
    body: QuizItemCreate,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course, module = await content.course_of_module(db, module_id)
    lesson = await content.create_quiz_item(
        db,
        course,
        user,
        module_id,
        title=body.title or "Bài tập mới",
        duration_minutes=body.duration_minutes or 15,
        due_at=body.due_at,
    )
    if body.after_id is not None:
        items = (
            await db.execute(
                select(CourseVersionItem)
                .where(CourseVersionItem.module_id == module.id)
                .order_by(CourseVersionItem.position)
            )
        ).scalars().all()
        ordered = [item.lesson_id for item in items if item.lesson_id != lesson.id]
        try:
            index = ordered.index(str(body.after_id)) + 1
        except ValueError:
            index = len(ordered)
        ordered.insert(index, lesson.id)
        await content.reorder_items(db, course, user, module_id, ordered)
    await db.commit()
    draft = await content.get_draft_version(db, course, user)
    assert draft is not None
    item = (
        await db.execute(
            select(CourseVersionItem).where(
                CourseVersionItem.course_version_id == draft.id,
                CourseVersionItem.lesson_id == lesson.id,
            )
        )
    ).scalar_one()
    lesson_version = await content.ensure_draft_lesson_version(db, item, user)
    return LessonNodeOut(
        id=lesson.id,
        title=lesson_version.title,
        kind="quiz",
        slides=0,
        quiz_id=lesson_version.id,
        quiz_status="draft",
        question_count=0,
        duration_minutes=body.duration_minutes or 15,
        due_at=body.due_at,
        lesson_version_id=lesson_version.id,
        item_id=item.id,
    )


@router.post("/teacher/modules/{module_id}/items/reorder", response_model=dict)
async def reorder_module_items(
    module_id: str,
    body: ModuleItemsReorderIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course, _ = await content.course_of_module(db, module_id)
    await content.reorder_items(
        db, course, user, module_id, [item.id for item in body.items]
    )
    await db.commit()
    return {"ok": True}
