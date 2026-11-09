"""Draft tree and published outline views."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload

from app.models.auth import User
from app.models.course import (
    Course,
    CourseVersionItem,
    CourseVersionModule,
    Lesson,
    LessonVersion,
    LessonVersionSlide,
)
from app.models.media import SlideDocument
from app.models.quiz import QuizSpec
from app.schemas.course import (
    CourseOutlineOut,
    LessonItemOut,
    LessonNodeOut,
    ModuleItemOut,
    ModuleNodeOut,
)
from app.services.content.common import (
    _not_found,
    get_draft_version,
    get_published_version,
)
from app.services.content.publish import published_quiz_lesson_ids


async def _outline_item_rows(db: AsyncSession, course_version_id: str):
    """Một query cho toàn bộ item + lesson + quiz + số slide của outline."""
    slide_counts = (
        select(
            LessonVersionSlide.lesson_version_id,
            func.count(LessonVersionSlide.id).label("slide_count"),
        )
        .group_by(LessonVersionSlide.lesson_version_id)
        .subquery()
    )
    return (
        await db.execute(
            select(
                CourseVersionItem,
                Lesson,
                LessonVersion,
                QuizSpec,
                func.coalesce(slide_counts.c.slide_count, 0),
            )
            .join(Lesson, Lesson.id == CourseVersionItem.lesson_id)
            .join(
                LessonVersion,
                LessonVersion.id == CourseVersionItem.lesson_version_id,
            )
            .outerjoin(QuizSpec, QuizSpec.lesson_version_id == LessonVersion.id)
            .outerjoin(
                slide_counts,
                slide_counts.c.lesson_version_id == LessonVersion.id,
            )
            .where(CourseVersionItem.course_version_id == course_version_id)
            .order_by(CourseVersionItem.position)
            .options(
                raiseload(Lesson.versions),
                raiseload(Lesson.slides),
                raiseload(LessonVersion.slides),
            )
        )
    ).all()


async def get_draft_tree(
    db: AsyncSession, course: Course, user: User
) -> list[ModuleNodeOut]:
    draft = await get_draft_version(db, course, user)
    assert draft is not None
    modules = (
        await db.execute(
            select(CourseVersionModule)
            .where(CourseVersionModule.course_version_id == draft.id)
            .order_by(CourseVersionModule.position)
            .options(raiseload(CourseVersionModule.items))
        )
    ).scalars().all()
    rows = await _outline_item_rows(db, draft.id)
    by_module: dict[str, list] = {}
    for row in rows:
        by_module.setdefault(row[0].module_id, []).append(row)

    # Bài tập đã có trong bản xuất bản thì sinh viên đã thấy, kể cả khi giáo
    # viên đang sửa một lesson version nháp mới.
    published_quiz_lessons = await published_quiz_lesson_ids(db, course)

    # Đếm trạng thái index RAG theo từng lesson version trong một query.
    lesson_version_ids = [row[2].id for row in rows]
    ingest_counts: dict[str, tuple[int, int, int]] = {}
    if lesson_version_ids:
        count_rows = (
            await db.execute(
                select(
                    LessonVersionSlide.lesson_version_id,
                    func.count(SlideDocument.slide_version_id)
                    .filter(SlideDocument.ingestion_state == "ready")
                    .label("ready"),
                    func.count(SlideDocument.slide_version_id)
                    .filter(SlideDocument.ingestion_state == "failed")
                    .label("failed"),
                    func.count(SlideDocument.slide_version_id)
                    .filter(SlideDocument.ingestion_state == "pending")
                    .label("pending"),
                )
                .outerjoin(
                    SlideDocument,
                    SlideDocument.slide_version_id
                    == LessonVersionSlide.slide_version_id,
                )
                .where(
                    LessonVersionSlide.lesson_version_id.in_(lesson_version_ids)
                )
                .group_by(LessonVersionSlide.lesson_version_id)
            )
        ).all()
        ingest_counts = {
            row.lesson_version_id: (
                int(row.ready),
                int(row.failed),
                int(row.pending),
            )
            for row in count_rows
        }

    out: list[ModuleNodeOut] = []
    for module in modules:
        lessons: list[LessonNodeOut] = []
        for item, lesson, lesson_version, quiz, slide_count in by_module.get(
            module.id, []
        ):
            slides_ready, slides_failed, _ = ingest_counts.get(
                lesson_version.id, (0, 0, 0)
            )
            # Slide chưa có row trong slide_documents cũng coi như đang chờ
            # index để UI poll và checklist xuất bản phản ánh đúng.
            slides_pending = max(
                0, int(slide_count) - slides_ready - slides_failed
            )
            lessons.append(
                LessonNodeOut(
                    id=lesson.id,
                    title=lesson_version.title,
                    kind=lesson.kind,
                    slides=int(slide_count),
                    slides_ready=slides_ready,
                    slides_failed=slides_failed,
                    slides_pending=slides_pending,
                    quiz_id=lesson_version.id if quiz else None,
                    # Trạng thái bài tập phản ánh việc sinh viên có thấy bài
                    # trong bản xuất bản hay không, không phải state của
                    # lesson version nháp đang được sửa.
                    quiz_status=(
                        (
                            "published"
                            if lesson.id in published_quiz_lessons
                            else "draft"
                        )
                        if quiz
                        else None
                    ),
                    question_count=len(quiz.questions) if quiz else 0,
                    duration_minutes=quiz.duration_minutes if quiz else None,
                    due_at=quiz.due_at if quiz else None,
                    lesson_version_id=lesson_version.id,
                    item_id=item.id,
                )
            )
        out.append(
            ModuleNodeOut(
                id=module.id,
                title=module.title,
                lessons=lessons,
                module_key=str(module.module_key),
                generation=draft.generation,
            )
        )
    return out


async def get_published_outline(
    db: AsyncSession, course: Course
) -> CourseOutlineOut:
    published = await get_published_version(db, course)
    if published is None:
        raise _not_found("Khóa học chưa được xuất bản")
    modules = (
        await db.execute(
            select(CourseVersionModule)
            .where(CourseVersionModule.course_version_id == published.id)
            .order_by(CourseVersionModule.position)
            .options(raiseload(CourseVersionModule.items))
        )
    ).scalars().all()
    rows = await _outline_item_rows(db, published.id)
    by_module: dict[str, list] = {}
    for row in rows:
        by_module.setdefault(row[0].module_id, []).append(row)

    out_modules: list[ModuleItemOut] = []
    for module in modules:
        lessons: list[LessonItemOut] = []
        for item, lesson, lesson_version, quiz, slide_count in by_module.get(
            module.id, []
        ):
            lessons.append(
                LessonItemOut(
                    id=lesson.id,
                    title=lesson_version.title,
                    kind=lesson.kind,
                    slide_count=int(slide_count),
                    quiz_id=lesson_version.id if quiz else None,
                    quiz_status="published" if quiz else None,
                    question_count=len(quiz.questions) if quiz else 0,
                    duration_minutes=quiz.duration_minutes if quiz else None,
                    due_at=quiz.due_at if quiz else None,
                )
            )
        out_modules.append(
            ModuleItemOut(
                id=module.id,
                order_index=module.position,
                title=module.title,
                lessons=lessons,
            )
        )
    return CourseOutlineOut(
        id=course.id,
        title=published.title,
        modules=out_modules,
        show_gaze_dot=course.show_gaze_dot,
        require_calibration=course.require_calibration,
    )
