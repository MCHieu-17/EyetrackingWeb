"""Draft tree and published outline."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.course import Course, CourseModule, Lesson, Slide
from app.schemas.course import (
    CourseOutlineOut,
    LessonItemOut,
    LessonNodeOut,
    ModuleItemOut,
    ModuleNodeOut,
)
from app.services.content.common import _not_found


async def _modules_with_lessons(
    db: AsyncSession, course_id: str
) -> list[tuple[CourseModule, list[tuple[Lesson, int, int, int, int]]]]:
    modules = (
        await db.execute(
            select(CourseModule)
            .where(CourseModule.course_id == course_id)
            .order_by(CourseModule.position)
        )
    ).scalars().all()
    if not modules:
        return []

    stats = (
        select(
            Slide.lesson_id,
            func.count(Slide.id).label("slide_count"),
            func.count(Slide.id).filter(Slide.index_status == "ready").label("ready"),
            func.count(Slide.id).filter(Slide.index_status == "failed").label("failed"),
            func.count(Slide.id).filter(Slide.index_status == "pending").label("pending"),
        )
        .group_by(Slide.lesson_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(
                Lesson,
                func.coalesce(stats.c.slide_count, 0),
                func.coalesce(stats.c.ready, 0),
                func.coalesce(stats.c.failed, 0),
                func.coalesce(stats.c.pending, 0),
            )
            .outerjoin(stats, stats.c.lesson_id == Lesson.id)
            .where(Lesson.module_id.in_([module.id for module in modules]))
            .order_by(Lesson.position)
        )
    ).all()
    by_module: dict[str, list[tuple[Lesson, int, int, int, int]]] = {}
    for row in rows:
        by_module.setdefault(row[0].module_id, []).append(tuple(row))
    return [
        (
            module,
            sorted(
                by_module.get(module.id, []),
                key=lambda entry: entry[0].position,
            ),
        )
        for module in modules
    ]


def _quiz_meta(lesson: Lesson) -> dict:
    config = lesson.quiz_config or {}
    questions = config.get("questions") or []
    return {
        "question_count": len(questions) if isinstance(questions, list) else 0,
        "duration_minutes": config.get("durationMinutes"),
        "due_at": config.get("dueAt"),
        "quiz_status": config.get("status", "draft"),
    }


async def get_course_tree(
    db: AsyncSession, course: Course, user: User
) -> list[ModuleNodeOut]:
    out: list[ModuleNodeOut] = []
    for module, lessons in await _modules_with_lessons(db, course.id):
        nodes: list[LessonNodeOut] = []
        for lesson, slide_count, ready, failed, pending in lessons:
            quiz = _quiz_meta(lesson) if lesson.kind == "quiz" else {}
            nodes.append(
                LessonNodeOut(
                    id=lesson.id,
                    title=lesson.title,
                    kind=lesson.kind,
                    slides=int(slide_count),
                    slides_ready=int(ready),
                    slides_failed=int(failed),
                    slides_pending=int(pending),
                    quiz_id=lesson.id if lesson.kind == "quiz" else None,
                    quiz_status=quiz.get("quiz_status") if quiz else None,
                    question_count=quiz.get("question_count", 0) if quiz else 0,
                    duration_minutes=quiz.get("duration_minutes") if quiz else None,
                    due_at=quiz.get("due_at") if quiz else None,
                )
            )
        out.append(ModuleNodeOut(id=module.id, title=module.title, lessons=nodes))
    return out


async def get_published_outline(
    db: AsyncSession, course: Course
) -> CourseOutlineOut:
    if course.status != "published":
        raise _not_found("Khóa học chưa được xuất bản")
    modules: list[ModuleItemOut] = []
    for module, lessons in await _modules_with_lessons(db, course.id):
        items: list[LessonItemOut] = []
        for lesson, slide_count, *_ in lessons:
            quiz = _quiz_meta(lesson) if lesson.kind == "quiz" else {}
            items.append(
                LessonItemOut(
                    id=lesson.id,
                    title=lesson.title,
                    kind=lesson.kind,
                    slide_count=int(slide_count),
                    quiz_id=lesson.id if lesson.kind == "quiz" else None,
                    quiz_status=quiz.get("quiz_status") if quiz else None,
                    question_count=quiz.get("question_count", 0) if quiz else 0,
                    duration_minutes=quiz.get("duration_minutes") if quiz else None,
                    due_at=quiz.get("due_at") if quiz else None,
                )
            )
        modules.append(
            ModuleItemOut(
                id=module.id,
                order_index=module.position,
                title=module.title,
                lessons=items,
            )
        )
    return CourseOutlineOut(
        id=course.id,
        title=course.title,
        modules=modules,
        show_gaze_dot=course.show_gaze_dot,
        require_calibration=course.require_calibration,
    )
