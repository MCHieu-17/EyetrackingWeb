"""Validation and publishing without content versions."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.course import Course, CourseModule, Lesson, Slide
from app.models.media import MediaAsset
from app.services.content.common import _now


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
        option_ids = {str(option.get("id")) for option in (question.get("options") or [])}
        correct = {
            str(item) for item in (question.get("correctOptionIds") or [])
        }
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


async def validate_course(db: AsyncSession, course: Course) -> None:
    modules = (
        await db.execute(
            select(CourseModule)
            .where(CourseModule.course_id == course.id)
            .order_by(CourseModule.position)
        )
    ).scalars().all()
    if not modules:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "content_invalid", "message": "Khóa học chưa có chương"},
        )
    lessons = (
        await db.execute(
            select(Lesson)
            .where(Lesson.module_id.in_([module.id for module in modules]))
            .order_by(Lesson.position)
        )
    ).scalars().all()
    if not lessons:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "content_invalid", "message": "Khóa học chưa có nội dung"},
        )
    slide_stats = {
        lesson_id: (int(slide_count), int(not_ready))
        for lesson_id, slide_count, not_ready in (
            await db.execute(
                select(
                    Slide.lesson_id,
                    func.count(Slide.id),
                    func.count(Slide.id).filter(Slide.index_status != "ready"),
                )
                .where(Slide.lesson_id.in_([lesson.id for lesson in lessons]))
                .group_by(Slide.lesson_id)
            )
        ).all()
    }
    asset_ids = [lesson.pdf_asset_id for lesson in lessons if lesson.pdf_asset_id]
    assets = {
        asset.id: asset
        for asset in (
            await db.execute(select(MediaAsset).where(MediaAsset.id.in_(asset_ids)))
        ).scalars()
    }

    for lesson in lessons:
        if lesson.kind == "lesson":
            slide_count, not_ready = slide_stats.get(lesson.id, (0, 0))
            if not slide_count:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "content_invalid",
                        "message": f'Bài giảng "{lesson.title}" chưa có slide',
                    },
                )
            if not_ready:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "slides_not_indexed",
                        "message": (
                            f'Bài giảng "{lesson.title}" còn {not_ready} '
                            "trang chưa index xong cho trợ lý học tập. Vui lòng chờ "
                            "hệ thống xử lý hoặc bấm \"Thử lại index\"."
                        ),
                    },
                )
            asset = assets.get(lesson.pdf_asset_id or "")
            if asset is None or asset.state != "ready":
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "content_invalid",
                        "message": f'Slide của "{lesson.title}" chưa sẵn sàng',
                    },
                )
        else:
            config = lesson.quiz_config or {}
            _validate_questions(config.get("questions") or [])


async def publish_course(
    db: AsyncSession, course: Course, user: User
) -> Course:
    await db.execute(select(Course.id).where(Course.id == course.id).with_for_update())
    await validate_course(db, course)
    course.status = "published"
    course.published_at = _now()
    course.updated_at = _now()
    await db.flush()
    return course
