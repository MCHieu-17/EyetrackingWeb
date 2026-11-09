"""Lesson and quiz item CRUD, ordering."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.course import (
    Course,
    CourseVersion,
    CourseVersionItem,
    CourseVersionModule,
    Lesson,
    LessonVersion,
)
from app.models.quiz import QuizSpec
from app.services.content.common import (
    _not_found,
    bump_generation,
    get_draft_version,
)
from app.services.content.modules import _draft_module
from app.services.content.versions import ensure_draft_lesson_version


async def get_draft_item_for_lesson(
    db: AsyncSession, course: Course, lesson_id: str, user: User
) -> tuple[CourseVersion, CourseVersionItem]:
    return await _draft_item(db, course, lesson_id, user)


async def _draft_item(
    db: AsyncSession, course: Course, lesson_id: str, user: User
) -> tuple[CourseVersion, CourseVersionItem]:
    draft = await get_draft_version(db, course, user)
    assert draft is not None
    item = (
        await db.execute(
            select(CourseVersionItem).where(
                CourseVersionItem.course_version_id == draft.id,
                CourseVersionItem.lesson_id == lesson_id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise _not_found("Không tìm thấy bài học trong bản nháp")
    return draft, item


async def _next_item_position(db: AsyncSession, course_version_id: str) -> int:
    value = (
        await db.execute(
            select(func.coalesce(func.max(CourseVersionItem.position), -1) + 1).where(
                CourseVersionItem.course_version_id == course_version_id
            )
        )
    ).scalar_one()
    return int(value)


async def _renumber_items(
    db: AsyncSession, course_version_id: str, ordered_ids: list[str]
) -> None:
    items = (
        await db.execute(
            select(CourseVersionItem).where(
                CourseVersionItem.course_version_id == course_version_id
            )
        )
    ).scalars().all()
    by_lesson = {item.lesson_id: item for item in items}
    # position có CHECK >= 0 và UNIQUE (course_version_id, position); dùng
    # offset tạm thời thay vì số âm để tránh vi phạm constraint.
    offset = max((item.position for item in items), default=0) + len(items) + 1
    for index, item in enumerate(items):
        item.position = offset + index
    await db.flush()
    for index, lesson_id in enumerate(ordered_ids):
        by_lesson[lesson_id].position = index
    await db.flush()


async def create_lesson(
    db: AsyncSession, course: Course, user: User, module_id: str, title: str
) -> Lesson:
    draft, module = await _draft_module(db, course, module_id, user)
    lesson = Lesson(course_id=course.id, kind="lesson")
    db.add(lesson)
    await db.flush()
    lesson_version = LessonVersion(
        lesson_id=lesson.id,
        version_no=1,
        state="draft",
        title=title,
        created_by=user.id,
    )
    db.add(lesson_version)
    await db.flush()
    db.add(
        CourseVersionItem(
            course_version_id=draft.id,
            module_id=module.id,
            lesson_id=lesson.id,
            lesson_version_id=lesson_version.id,
            position=await _next_item_position(db, draft.id),
        )
    )
    bump_generation(draft)
    await db.flush()
    return lesson


async def create_quiz_item(
    db: AsyncSession,
    course: Course,
    user: User,
    module_id: str,
    *,
    title: str,
    duration_minutes: int,
    due_at: datetime | None,
) -> Lesson:
    draft, module = await _draft_module(db, course, module_id, user)
    lesson = Lesson(course_id=course.id, kind="quiz")
    db.add(lesson)
    await db.flush()
    lesson_version = LessonVersion(
        lesson_id=lesson.id,
        version_no=1,
        state="draft",
        title=title,
        created_by=user.id,
    )
    db.add(lesson_version)
    await db.flush()
    db.add(
        QuizSpec(
            lesson_version_id=lesson_version.id,
            instructions="",
            duration_minutes=duration_minutes,
            due_at=due_at,
            questions=[],
        )
    )
    db.add(
        CourseVersionItem(
            course_version_id=draft.id,
            module_id=module.id,
            lesson_id=lesson.id,
            lesson_version_id=lesson_version.id,
            position=await _next_item_position(db, draft.id),
        )
    )
    bump_generation(draft)
    await db.flush()
    return lesson


async def update_lesson(
    db: AsyncSession, course: Course, user: User, lesson_id: str, title: str
) -> LessonVersion:
    draft, item = await _draft_item(db, course, lesson_id, user)
    lesson_version = await ensure_draft_lesson_version(db, item, user)
    lesson_version.title = title
    bump_generation(draft)
    await db.flush()
    return lesson_version


async def delete_lesson(
    db: AsyncSession, course: Course, user: User, lesson_id: str
) -> None:
    draft, item = await _draft_item(db, course, lesson_id, user)
    await db.delete(item)
    bump_generation(draft)
    await db.flush()


async def reorder_items(
    db: AsyncSession,
    course: Course,
    user: User,
    module_id: str,
    ordered_lesson_ids: list[str],
) -> None:
    draft, module = await _draft_module(db, course, module_id, user)
    items = (
        await db.execute(
            select(CourseVersionItem)
            .where(CourseVersionItem.course_version_id == draft.id)
            .order_by(CourseVersionItem.position)
        )
    ).scalars().all()
    module_items = [item for item in items if item.module_id == module.id]
    by_lesson = {item.lesson_id: item for item in module_items}
    if set(ordered_lesson_ids) != set(by_lesson):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Danh sách item không khớp cấu trúc chương",
        )
    modules = (
        await db.execute(
            select(CourseVersionModule)
            .where(CourseVersionModule.course_version_id == draft.id)
            .order_by(CourseVersionModule.position)
        )
    ).scalars().all()
    global_order: list[str] = []
    for current in modules:
        if current.id == module.id:
            global_order.extend(ordered_lesson_ids)
        else:
            global_order.extend(
                item.lesson_id for item in items if item.module_id == current.id
            )
    await _renumber_items(db, draft.id, global_order)
    bump_generation(draft)
    await db.flush()
