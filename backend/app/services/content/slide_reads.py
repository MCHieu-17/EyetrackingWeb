"""Read DTO cho slide của bài học.

Tách khỏi import/convert để route và worker không phải import toàn bộ lifecycle.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.models.auth import User
from app.models.course import Course, Lesson, Slide
from app.models.media import MediaAsset
from app.schemas.course import SlideAdminOut, SlideOut
from app.services import media_storage
from app.services.content.common import _not_found, course_of_lesson


async def _lesson_and_asset(
    db: AsyncSession, lesson_id: str, lesson: Lesson | None = None
) -> tuple[Lesson, MediaAsset | None]:
    if lesson is None:
        _, lesson = await course_of_lesson(db, lesson_id)
    if lesson.id != lesson_id:
        raise _not_found("Không tìm thấy bài học")
    asset = await db.get(MediaAsset, lesson.pdf_asset_id) if lesson.pdf_asset_id else None
    return lesson, asset


async def _slides(db: AsyncSession, lesson_id: str) -> list[Slide]:
    return list(
        (
            await db.execute(
                select(Slide)
                .options(
                    load_only(
                        Slide.id,
                        Slide.title,
                        Slide.position,
                        Slide.page_number,
                        Slide.index_status,
                        Slide.index_error,
                    )
                )
                .where(Slide.lesson_id == lesson_id)
                .order_by(Slide.position)
            )
        ).scalars()
    )


async def list_lesson_slides_admin(
    db: AsyncSession,
    course: Course,
    user: User,
    lesson_id: str,
    *,
    lesson: Lesson | None = None,
) -> list[SlideAdminOut]:
    del course, user
    lesson, asset = await _lesson_and_asset(db, lesson_id, lesson)
    rows = await _slides(db, lesson.id)
    return [
        SlideAdminOut(
            id=slide.id,
            order_index=slide.position,
            title=slide.title or f"Slide {slide.position + 1}",
            pdf_url=media_storage.asset_file_url(asset.id) if asset else None,
            page_number=slide.page_number,
            page_count=asset.page_count if asset and asset.page_count else 1,
            source_format=asset.source_format if asset else None,
            embedding_status=slide.index_status,
            embedding_error=slide.index_error,
        )
        for slide in rows
    ]


async def get_lesson_contents(
    db: AsyncSession,
    course: Course | None,
    lesson_id: str,
    *,
    lesson: Lesson | None = None,
) -> list[SlideOut]:
    del course
    lesson, asset = await _lesson_and_asset(db, lesson_id, lesson)
    rows = await _slides(db, lesson.id)
    return [
        SlideOut(
            id=slide.id,
            title=slide.title or f"Slide {slide.position + 1}",
            pdf_url=media_storage.asset_file_url(asset.id) if asset else None,
            page_number=slide.page_number,
            page_count=asset.page_count if asset and asset.page_count else 1,
            source_format=asset.source_format if asset else None,
        )
        for slide in rows
    ]
