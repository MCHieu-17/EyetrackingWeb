"""Rebuild analysis runs cho course/lesson."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload

from app.api.deps import can_access_course
from app.models.aoi import AnalysisRun, AoiLayoutSnapshot, AoiSet
from app.models.auth import User
from app.models.course import (
    Course,
    CourseVersion,
    CourseVersionItem,
    LessonVersionSlide,
)
from app.models.gaze import ContentPresentation, GazeBatch, LearningSession
from app.services.analysis.common import _now
from app.services.analysis.runs import _create_run


async def rebuild_course(
    db: AsyncSession,
    user: User,
    *,
    course_id: str,
    lesson_id: str | None = None,
    from_time: datetime | None,
    to_time: datetime | None,
    algorithm_version: str,
) -> tuple[int, int, int]:
    course = await db.get(
        Course,
        course_id,
        options=[
            raiseload(Course.versions),
            raiseload(Course.enrollments),
            raiseload(Course.owner),
            raiseload(Course.creator),
        ],
    )
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    if not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    # Lấy session qua mọi course version (kể cả bản cũ) để rebuild dữ liệu lịch
    # sử vẫn đúng sau khi khóa học được publish lại.
    item_stmt = (
        select(CourseVersionItem.id)
        .join(
            CourseVersion,
            CourseVersion.id == CourseVersionItem.course_version_id,
        )
        .where(CourseVersion.course_id == course_id)
    )
    if lesson_id:
        item_stmt = item_stmt.where(CourseVersionItem.lesson_id == lesson_id)
    item_ids = list((await db.execute(item_stmt)).scalars().all())
    if not item_ids:
        return 0, 0, 0

    sessions = (
        await db.execute(
            select(LearningSession)
            .options(raiseload(LearningSession.presentations))
            .where(LearningSession.course_version_item_id.in_(item_ids))
            .order_by(LearningSession.started_at)
        )
    ).scalars().all()
    if not sessions:
        return 0, 0, 0

    session_ids = [session.id for session in sessions]
    presentations = (
        await db.execute(
            select(ContentPresentation)
            .where(ContentPresentation.session_id.in_(session_ids))
            .order_by(
                ContentPresentation.session_id,
                ContentPresentation.sequence_no,
            )
        )
    ).scalars().all()
    if not presentations:
        return 0, 0, 0

    presentation_ids = [presentation.id for presentation in presentations]

    batch_presentation_ids = set(
        (
            await db.execute(
                select(GazeBatch.presentation_id)
                .where(GazeBatch.presentation_id.in_(presentation_ids))
                .distinct()
            )
        ).scalars().all()
    )

    watermark_rows = (
        await db.execute(
            select(
                GazeBatch.id,
                GazeBatch.session_id,
                GazeBatch.presentation_id,
            )
            .ext(distinct_on(GazeBatch.session_id, GazeBatch.presentation_id))
            .where(GazeBatch.session_id.in_(session_ids))
            .order_by(
                GazeBatch.session_id,
                GazeBatch.presentation_id,
                GazeBatch.batch_no.desc(),
            )
        )
    ).all()
    watermarks = {
        (session_id, presentation_id): batch_id
        for batch_id, session_id, presentation_id in watermark_rows
    }

    # Slide AOI set: ưu tiên set gắn trực tiếp, fallback set published của slide.
    direct_slide_set_ids = list(
        {
            presentation.slide_aoi_set_id
            for presentation in presentations
            if presentation.slide_aoi_set_id
        }
    )
    existing_slide_set_ids = (
        set(
            (
                await db.execute(
                    select(AoiSet.id).where(
                        AoiSet.id.in_(direct_slide_set_ids)
                    )
                )
            ).scalars().all()
        )
        if direct_slide_set_ids
        else set()
    )

    slide_ids = list(
        {
            presentation.lesson_version_slide_id
            for presentation in presentations
            if presentation.lesson_version_slide_id
            and (
                not presentation.slide_aoi_set_id
                or presentation.slide_aoi_set_id not in existing_slide_set_ids
            )
        }
    )
    slide_version_by_slide_id: dict[str, str] = {}
    if slide_ids:
        slide_version_by_slide_id = dict(
            (
                await db.execute(
                    select(
                        LessonVersionSlide.id,
                        LessonVersionSlide.slide_version_id,
                    ).where(LessonVersionSlide.id.in_(slide_ids))
                )
            ).all()
        )
    slide_version_ids = list(set(slide_version_by_slide_id.values()))
    published_slide_set_by_version: dict[str, str] = {}
    if slide_version_ids:
        published_slide_set_by_version = dict(
            (
                await db.execute(
                    select(AoiSet.slide_version_id, AoiSet.id).where(
                        AoiSet.state == "published",
                        AoiSet.slide_version_id.in_(slide_version_ids),
                    )
                )
            ).all()
        )

    # UI AOI set: snapshot mới nhất có ui_aoi_set_id, fallback reader-v1.
    snapshot_rows = (
        await db.execute(
            select(
                AoiLayoutSnapshot.presentation_id,
                AoiLayoutSnapshot.ui_aoi_set_id,
            )
            .where(
                AoiLayoutSnapshot.presentation_id.in_(presentation_ids),
                AoiLayoutSnapshot.ui_aoi_set_id.is_not(None),
            )
            .order_by(
                AoiLayoutSnapshot.presentation_id,
                AoiLayoutSnapshot.captured_at.desc(),
            )
        )
    ).all()
    snapshot_ui_set_by_presentation: dict[str, str] = {}
    for presentation_id, ui_set_id in snapshot_rows:
        snapshot_ui_set_by_presentation.setdefault(presentation_id, ui_set_id)
    snapshot_ui_set_ids = list(set(snapshot_ui_set_by_presentation.values()))
    existing_ui_set_ids = (
        set(
            (
                await db.execute(
                    select(AoiSet.id).where(AoiSet.id.in_(snapshot_ui_set_ids))
                )
            ).scalars().all()
        )
        if snapshot_ui_set_ids
        else set()
    )
    fallback_ui_set_id = (
        await db.execute(
            select(AoiSet.id)
            .where(
                AoiSet.state == "published",
                AoiSet.ui_schema_version == "reader-v1",
            )
            .limit(1)
        )
    ).scalar_one_or_none()

    existing_runs = set(
        (
            await db.execute(
                select(
                    AnalysisRun.presentation_id,
                    AnalysisRun.aoi_set_id,
                ).where(
                    AnalysisRun.presentation_id.in_(presentation_ids),
                    AnalysisRun.algorithm_version == algorithm_version,
                    AnalysisRun.status.in_(("pending", "running")),
                )
            )
        ).all()
    )

    presentations_by_session: dict[str, list[ContentPresentation]] = {}
    for presentation in presentations:
        presentations_by_session.setdefault(
            presentation.session_id, []
        ).append(presentation)

    runs = 0
    for session in sessions:
        for presentation in presentations_by_session.get(session.id, []):
            if presentation.id not in batch_presentation_ids:
                continue

            start = max(
                from_time or session.started_at,
                presentation.started_at,
            )
            end = min(
                to_time or session.ended_at or _now(),
                presentation.ended_at or _now(),
            )
            if end <= start:
                continue

            watermark_id = watermarks.get((session.id, presentation.id))

            if presentation.surface == "lesson":
                slide_set_id = None
                if (
                    presentation.slide_aoi_set_id
                    and presentation.slide_aoi_set_id in existing_slide_set_ids
                ):
                    slide_set_id = presentation.slide_aoi_set_id
                elif presentation.lesson_version_slide_id:
                    slide_version_id = slide_version_by_slide_id.get(
                        presentation.lesson_version_slide_id
                    )
                    if slide_version_id:
                        slide_set_id = published_slide_set_by_version.get(
                            slide_version_id
                        )
                if slide_set_id is not None:
                    duplicate = (
                        presentation.id,
                        slide_set_id,
                    ) in existing_runs
                    run = await _create_run(
                        db,
                        session=session,
                        presentation=presentation,
                        aoi_set_id=slide_set_id,
                        start=start,
                        end=end,
                        algorithm_version=algorithm_version,
                        watermark_id=watermark_id,
                        duplicate=duplicate,
                    )
                    if run is not None:
                        existing_runs.add((presentation.id, slide_set_id))
                        runs += 1

            ui_set_id = snapshot_ui_set_by_presentation.get(presentation.id)
            if ui_set_id not in existing_ui_set_ids:
                ui_set_id = fallback_ui_set_id
            if ui_set_id is not None:
                duplicate = (presentation.id, ui_set_id) in existing_runs
                run = await _create_run(
                    db,
                    session=session,
                    presentation=presentation,
                    aoi_set_id=ui_set_id,
                    start=start,
                    end=end,
                    algorithm_version=algorithm_version,
                    watermark_id=watermark_id,
                    duplicate=duplicate,
                )
                if run is not None:
                    existing_runs.add((presentation.id, ui_set_id))
                    runs += 1
    return runs, 0, 0
