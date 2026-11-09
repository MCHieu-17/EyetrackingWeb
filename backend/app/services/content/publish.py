"""Draft validation and course publishing."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload

from app.models.auth import User
from app.models.course import (
    ContentAuditEvent,
    Course,
    CourseVersion,
    CourseVersionItem,
    Lesson,
    LessonVersion,
    LessonVersionSlide,
    SlideVersion,
)
from app.models.media import MediaAsset, SlideDocument
from app.models.quiz import QuizSpec
from app.services.content.common import (
    _now,
    check_generation,
    get_draft_version,
)


def _validate_questions(questions: list[dict]) -> None:
    if not isinstance(questions, list) or not questions:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "quiz_not_ready", "message": "Bài tập chưa có câu hỏi"},
        )
    seen: set[str] = set()
    for question in questions:
        qid = str(question.get("id") or "")
        if not qid or qid in seen:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"code": "quiz_not_ready", "message": "Câu hỏi thiếu ID hoặc trùng ID"},
            )
        seen.add(qid)
        options = question.get("options") or []
        option_ids = {str(option.get("id")) for option in options}
        correct = {str(item) for item in (question.get("correctOptionIds") or [])}
        if not option_ids or not correct or not correct <= option_ids:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "quiz_not_ready",
                    "message": f"Câu hỏi {qid} thiếu đáp án hợp lệ",
                },
            )
        if float(question.get("points") or 0) <= 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "quiz_not_ready",
                    "message": f"Câu hỏi {qid} phải có điểm > 0",
                },
            )


async def validate_draft(db: AsyncSession, draft: CourseVersion) -> None:
    items = (
        await db.execute(
            select(CourseVersionItem)
            .where(CourseVersionItem.course_version_id == draft.id)
            .order_by(CourseVersionItem.position)
        )
    ).scalars().all()
    for item in items:
        lesson = await db.get(
            Lesson,
            item.lesson_id,
            options=[
                raiseload(Lesson.versions),
                raiseload(Lesson.slides),
            ],
        )
        lesson_version = await db.get(
            LessonVersion,
            item.lesson_version_id,
            options=[raiseload(LessonVersion.slides)],
        )
        if lesson is None or lesson_version is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"code": "content_invalid", "message": "Item thiếu bài học/phiên bản"},
            )
        if lesson.kind == "lesson":
            slides = (
                await db.execute(
                    select(LessonVersionSlide)
                    .where(
                        LessonVersionSlide.lesson_version_id == lesson_version.id
                    )
                    .options(raiseload(LessonVersionSlide.slide_version))
                )
            ).scalars().all()
            if not slides:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "content_invalid",
                        "message": f'Bài giảng "{lesson_version.title}" chưa có slide',
                    },
                )
            slide_version_ids = list(
                dict.fromkeys(slide.slide_version_id for slide in slides)
            )
            documents = (
                await db.execute(
                    select(SlideDocument).where(
                        SlideDocument.slide_version_id.in_(slide_version_ids)
                    )
                )
            ).scalars().all()
            by_slide_version = {
                document.slide_version_id: document for document in documents
            }
            not_indexed = [
                slide_version_id
                for slide_version_id in slide_version_ids
                if (
                    by_slide_version.get(slide_version_id) is None
                    or by_slide_version[slide_version_id].ingestion_state != "ready"
                )
            ]
            if not_indexed:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "slides_not_indexed",
                        "message": (
                            f'Bài giảng "{lesson_version.title}" còn '
                            f"{len(not_indexed)} trang chưa index xong cho trợ lý "
                            "học tập. Vui lòng chờ hệ thống xử lý hoặc bấm "
                            '"Thử lại index" trong trình soạn bài giảng.'
                        ),
                    },
                )
            for slide in slides:
                slide_version = await db.get(
                    SlideVersion,
                    slide.slide_version_id,
                    options=[raiseload(SlideVersion.source_pdf_asset)],
                )
                asset = (
                    await db.get(MediaAsset, slide_version.source_pdf_asset_id)
                    if slide_version
                    else None
                )
                if asset is None or asset.state != "ready":
                    raise HTTPException(
                        status.HTTP_400_BAD_REQUEST,
                        detail={
                            "code": "content_invalid",
                            "message": f'Slide của "{lesson_version.title}" chưa sẵn sàng',
                        },
                    )
        else:
            quiz = await db.get(QuizSpec, lesson_version.id)
            if quiz is None:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "quiz_not_ready",
                        "message": f'Bài tập "{lesson_version.title}" chưa có đề',
                    },
                )
            _validate_questions(quiz.questions)


async def publish_course(
    db: AsyncSession, course: Course, user: User, expected_generation: int | None
) -> CourseVersion:
    # Khóa course để chống publish/edit đồng thời.
    await db.execute(select(Course.id).where(Course.id == course.id).with_for_update())
    draft = await get_draft_version(db, course, user)
    assert draft is not None
    check_generation(draft, expected_generation)
    await validate_draft(db, draft)

    # Publish toàn bộ lesson version đang được draft tham chiếu. View published
    # outline và chatbot chỉ đọc lesson version state='published'.
    lesson_version_ids = (
        await db.execute(
            select(CourseVersionItem.lesson_version_id)
            .where(CourseVersionItem.course_version_id == draft.id)
            .distinct()
        )
    ).scalars().all()
    for lesson_version_id in lesson_version_ids:
        lesson_version = await db.get(
            LessonVersion,
            lesson_version_id,
            options=[raiseload(LessonVersion.slides)],
        )
        if lesson_version is not None and lesson_version.state == "draft":
            lesson_version.state = "published"
            lesson_version.published_at = _now()
            lesson_version.published_by = user.id

    draft.state = "published"
    draft.published_at = _now()
    draft.published_by = user.id
    # Flush version state trước để trigger courses.published_version_id thấy
    # version đã published trong cùng transaction.
    await db.flush()
    course.published_version_id = draft.id
    course.updated_at = _now()
    db.add(
        ContentAuditEvent(
            actor_id=user.id,
            course_id=course.id,
            course_version_id=draft.id,
            action="publish",
            request_id=None,
        )
    )
    await db.flush()
    return draft


async def published_quiz_lesson_ids(
    db: AsyncSession, course: Course
) -> set[str]:
    """ID các bài tập đang hiển thị với sinh viên trong bản xuất bản.

    Sinh viên chỉ thấy quiz thuộc course version đã publish. Trạng thái
    `lesson_versions.state` của bản nháp không quyết định việc này: khi giáo
    viên sửa quiz, hệ thống tạo lesson version nháp mới nhưng bản đã publish
    vẫn là bản sinh viên đang thấy cho tới khi xuất bản lại.
    """
    if not course.published_version_id:
        return set()
    rows = await db.execute(
        select(CourseVersionItem.lesson_id)
        .join(Lesson, Lesson.id == CourseVersionItem.lesson_id)
        .join(
            QuizSpec,
            QuizSpec.lesson_version_id == CourseVersionItem.lesson_version_id,
        )
        .where(
            CourseVersionItem.course_version_id == course.published_version_id,
            Lesson.kind == "quiz",
        )
    )
    return set(rows.scalars().all())
