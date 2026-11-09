"""Course/lesson version cloning and draft resolution."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload

from app.models.auth import User
from app.models.course import (
    CourseVersion,
    CourseVersionItem,
    CourseVersionModule,
    LessonVersion,
    LessonVersionSlide,
)
from app.models.quiz import QuizSpec
from app.services.content.common import _not_found


async def clone_course_version(
    db: AsyncSession, source: CourseVersion, user: User
) -> CourseVersion:
    max_no = (
        await db.execute(
            select(func.coalesce(func.max(CourseVersion.version_no), 0)).where(
                CourseVersion.course_id == source.course_id
            )
        )
    ).scalar_one()
    draft = CourseVersion(
        course_id=source.course_id,
        version_no=max_no + 1,
        state="draft",
        generation=1,
        title=source.title,
        description=source.description,
        thumbnail_asset_id=source.thumbnail_asset_id,
        created_by=user.id,
    )
    db.add(draft)
    await db.flush()

    source_modules = (
        await db.execute(
            select(CourseVersionModule)
            .where(CourseVersionModule.course_version_id == source.id)
            .order_by(CourseVersionModule.position)
            .options(raiseload(CourseVersionModule.items))
        )
    ).scalars().all()
    module_map: dict[str, CourseVersionModule] = {}
    for module in source_modules:
        cloned = CourseVersionModule(
            course_version_id=draft.id,
            module_key=module.module_key,
            title=module.title,
            position=module.position,
        )
        db.add(cloned)
        await db.flush()
        module_map[module.id] = cloned

    source_items = (
        await db.execute(
            select(CourseVersionItem)
            .where(CourseVersionItem.course_version_id == source.id)
            .order_by(CourseVersionItem.position)
        )
    ).scalars().all()
    for item in source_items:
        db.add(
            CourseVersionItem(
                course_version_id=draft.id,
                module_id=module_map[item.module_id].id,
                lesson_id=item.lesson_id,
                lesson_version_id=item.lesson_version_id,
                position=item.position,
            )
        )
    await db.flush()
    return draft


async def clone_lesson_version(
    db: AsyncSession, source: LessonVersion, user: User
) -> LessonVersion:
    max_no = (
        await db.execute(
            select(func.coalesce(func.max(LessonVersion.version_no), 0)).where(
                LessonVersion.lesson_id == source.lesson_id
            )
        )
    ).scalar_one()
    draft = LessonVersion(
        lesson_id=source.lesson_id,
        version_no=max_no + 1,
        state="draft",
        title=source.title,
        created_by=user.id,
    )
    db.add(draft)
    await db.flush()

    source_slides = (
        await db.execute(
            select(LessonVersionSlide)
            .where(LessonVersionSlide.lesson_version_id == source.id)
            .order_by(LessonVersionSlide.position)
            .options(raiseload(LessonVersionSlide.slide_version))
        )
    ).scalars().all()
    for slide in source_slides:
        db.add(
            LessonVersionSlide(
                lesson_version_id=draft.id,
                slide_id=slide.slide_id,
                slide_version_id=slide.slide_version_id,
                position=slide.position,
                title=slide.title,
            )
        )

    source_quiz = await db.get(QuizSpec, source.id)
    if source_quiz is not None:
        db.add(
            QuizSpec(
                lesson_version_id=draft.id,
                instructions=source_quiz.instructions,
                duration_minutes=source_quiz.duration_minutes,
                due_at=source_quiz.due_at,
                allow_retry=source_quiz.allow_retry,
                allow_chatbot=source_quiz.allow_chatbot,
                questions=source_quiz.questions,
            )
        )
    await db.flush()
    return draft


async def ensure_draft_lesson_version(
    db: AsyncSession, item: CourseVersionItem, user: User
) -> LessonVersion:
    lesson_version = await db.get(
        LessonVersion,
        item.lesson_version_id,
        options=[raiseload(LessonVersion.slides)],
    )
    if lesson_version is None:
        raise _not_found("Không tìm thấy phiên bản bài học")
    if lesson_version.state == "draft":
        return lesson_version
    draft = await clone_lesson_version(db, lesson_version, user)
    item.lesson_version_id = draft.id
    await db.flush()
    return draft
