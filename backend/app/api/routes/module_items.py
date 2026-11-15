from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import can_manage_course, require_roles
from app.db.session import get_db
from app.models.auth import User
from app.models.course import Lesson
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
    if not await can_manage_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
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
                select(Lesson)
                .where(Lesson.module_id == module.id)
                .order_by(Lesson.position)
            )
        ).scalars().all()
        ordered = [item.id for item in items if item.id != lesson.id]
        try:
            index = ordered.index(str(body.after_id)) + 1
        except ValueError:
            index = len(ordered)
        ordered.insert(index, lesson.id)
        await content.reorder_items(db, course, user, module_id, ordered)
    await db.commit()
    config = lesson.quiz_config or {}
    return LessonNodeOut(
        id=lesson.id,
        title=lesson.title,
        kind="quiz",
        slides=0,
        quiz_id=lesson.id,
        quiz_status=config.get("status", "draft"),
        question_count=0,
        duration_minutes=body.duration_minutes or 15,
        due_at=body.due_at,
    )


@router.post("/teacher/modules/{module_id}/items/reorder", response_model=dict)
async def reorder_module_items(
    module_id: str,
    body: ModuleItemsReorderIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course, _ = await content.course_of_module(db, module_id)
    if not await can_manage_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    await content.reorder_items(
        db, course, user, module_id, [item.id for item in body.items]
    )
    await db.commit()
    return {"ok": True}
