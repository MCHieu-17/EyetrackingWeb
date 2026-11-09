"""Analysis runs: run-scoped AOI hits + presentation metrics + streaming export.

Mỗi presentation được phân tích theo từng scope:
  * slide  — bộ vùng gắn với slide version đã dùng lúc học;
  * ui     — bộ vùng giao diện đã dùng trong layout snapshot.

Mẫu gaze không rơi vào vùng lá nào được gán `no_label`.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload

from app.api.deps import can_access_course
from app.db.session import SessionLocal
from app.models.aoi import (
    AnalysisRun,
    AoiDefinition,
    AoiHit,
    AoiLayoutSnapshot,
    AoiSet,
    PresentationMetric,
)
from app.models.auth import User
from app.models.calibration import Calibration, Device
from app.models.course import (
    Course,
    CourseVersion,
    CourseVersionItem,
    Enrollment,
    Lesson,
    LessonVersion,
    LessonVersionSlide,
)
from app.models.gaze import (
    ContentPresentation,
    GazeBatch,
    LearningSession,
)
from app.schemas.aoi import (
    AnalysisRunOut,
    AnalysisRunResultOut,
    PresentationMetricOut,
)
from app.services import metrics

NO_LABEL_CODE = "no_label"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _run_out(row: AnalysisRun) -> AnalysisRunOut:
    return AnalysisRunOut(
        id=row.id,
        session_id=row.session_id,
        presentation_id=row.presentation_id,
        aoi_set_id=row.aoi_set_id,
        from_time=row.from_time,
        to_time=row.to_time,
        batch_watermark=row.batch_watermark,
        algorithm_version=row.algorithm_version,
        status=row.status,
        error=row.error,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


async def _watermark(
    db: AsyncSession, session_id: str, presentation_id: str | None = None
) -> GazeBatch | None:
    stmt = select(GazeBatch).where(GazeBatch.session_id == session_id)
    if presentation_id:
        stmt = stmt.where(GazeBatch.presentation_id == presentation_id)
    return (
        await db.execute(stmt.order_by(GazeBatch.batch_no.desc()).limit(1))
    ).scalar_one_or_none()


def _filters(
    run: AnalysisRun,
    watermark_no: int | None,
    *,
    alias: str = "gs",
    batch_alias: str = "gb",
) -> tuple[str, dict]:
    conditions = [
        f"{alias}.session_id = :session_id",
        f"{alias}.event_time >= :from_time",
        f"{alias}.event_time < :to_time",
        f"{alias}.status = 'ok'",
        f"{alias}.viewport_x IS NOT NULL",
        f"{alias}.viewport_y IS NOT NULL",
    ]
    params: dict = {
        "session_id": run.session_id,
        "from_time": run.from_time,
        "to_time": run.to_time,
        "aoi_set_id": run.aoi_set_id,
        "run_id": run.id,
    }
    if run.presentation_id:
        conditions.append(f"{batch_alias}.presentation_id = :presentation_id")
        params["presentation_id"] = run.presentation_id
    if watermark_no is not None:
        conditions.append(f"{batch_alias}.batch_no <= :watermark_no")
        params["watermark_no"] = watermark_no
    return " AND ".join(conditions), params


async def _no_label_id(db: AsyncSession, set_id: str) -> str | None:
    return (
        await db.execute(
            select(AoiDefinition.id).where(
                AoiDefinition.aoi_set_id == set_id,
                AoiDefinition.code == NO_LABEL_CODE,
            )
        )
    ).scalar_one_or_none()


async def _insert_slide_hits(
    db: AsyncSession, run: AnalysisRun, watermark_no: int | None
) -> int:
    where, params = _filters(run, watermark_no)
    mapped = f"""
        WITH mapped AS (
            SELECT
                gs.id,
                gs.event_time,
                (
                    gs.viewport_x
                    - COALESCE((als.image_transform->>'left')::float, 0)
                ) / NULLIF(COALESCE((als.image_transform->>'width')::float, 1), 0) AS x,
                (
                    gs.viewport_y
                    - COALESCE((als.image_transform->>'top')::float, 0)
                ) / NULLIF(COALESCE((als.image_transform->>'height')::float, 1), 0) AS y
            FROM gaze_samples gs
            JOIN gaze_batches gb ON gb.id = gs.batch_id
            LEFT JOIN aoi_layout_snapshots als ON als.id = gb.layout_snapshot_id
            WHERE {where}
        )
    """

    # Mỗi sample chỉ nhận đúng một leaf hit. Thứ tự ưu tiên: vùng tự vẽ >
    # TEXT > TABLE > IMAGE > hình vẽ > còn lại. Nhờ vậy text đè lên ảnh sẽ
    # được tính là TEXT thay vì cả hai.
    leaf_sql = mapped + """
        , ranked AS (
            SELECT
                m.id,
                m.event_time,
                ad.id AS definition_id,
                ROW_NUMBER() OVER (
                    PARTITION BY m.id, m.event_time
                    ORDER BY
                        CASE ad.kind
                            WHEN 'custom' THEN 1
                            WHEN 'text' THEN 2
                            WHEN 'table' THEN 3
                            WHEN 'image' THEN 4
                            WHEN 'drawing' THEN 5
                            ELSE 6
                        END,
                        (
                            (ad.geometry->>'xMax')::float
                            - (ad.geometry->>'xMin')::float
                        ) * (
                            (ad.geometry->>'yMax')::float
                            - (ad.geometry->>'yMin')::float
                        )
                ) AS rn
            FROM mapped m
            JOIN aoi_definitions ad ON ad.aoi_set_id = :aoi_set_id
            WHERE ad.is_container = false
              AND ad.is_active = true
              AND ad.code <> 'no_label'
              AND m.x BETWEEN (ad.geometry->>'xMin')::float
                          AND (ad.geometry->>'xMax')::float
              AND m.y BETWEEN (ad.geometry->>'yMin')::float
                          AND (ad.geometry->>'yMax')::float
        )
        INSERT INTO aoi_hits (run_id, sample_id, event_time, definition_id)
        SELECT :run_id, id, event_time, definition_id
        FROM ranked
        WHERE rn = 1
        ON CONFLICT DO NOTHING
    """
    leaf = await db.execute(text(leaf_sql), params)

    container_sql = mapped + """
        INSERT INTO aoi_hits (run_id, sample_id, event_time, definition_id)
        SELECT :run_id, m.id, m.event_time, ad.id
        FROM mapped m
        JOIN aoi_definitions ad ON ad.aoi_set_id = :aoi_set_id
        WHERE ad.is_container = true
          AND ad.is_active = true
          AND m.x BETWEEN (ad.geometry->>'xMin')::float
                      AND (ad.geometry->>'xMax')::float
          AND m.y BETWEEN (ad.geometry->>'yMin')::float
                      AND (ad.geometry->>'yMax')::float
        ON CONFLICT DO NOTHING
    """
    container = await db.execute(text(container_sql), params)

    no_label_id = await _no_label_id(db, run.aoi_set_id)
    no_label_count = 0
    if no_label_id is not None:
        no_label_sql = mapped + """
            INSERT INTO aoi_hits (run_id, sample_id, event_time, definition_id)
            SELECT :run_id, m.id, m.event_time, :no_label_id
            FROM mapped m
            WHERE m.x BETWEEN 0 AND 1
              AND m.y BETWEEN 0 AND 1
              AND NOT EXISTS (
                  SELECT 1
                  FROM aoi_hits ah
                  JOIN aoi_definitions ad ON ad.id = ah.definition_id
                  WHERE ah.run_id = :run_id
                    AND ah.sample_id = m.id
                    AND ah.event_time = m.event_time
                    AND ad.is_container = false
                    AND ad.is_active = true
                    AND ad.code <> 'no_label'
              )
            ON CONFLICT DO NOTHING
        """
        no_label = await db.execute(
            text(no_label_sql), {**params, "no_label_id": no_label_id}
        )
        no_label_count = no_label.rowcount or 0

    return (leaf.rowcount or 0) + (container.rowcount or 0) + no_label_count


async def _insert_ui_hits(
    db: AsyncSession, run: AnalysisRun, watermark_no: int | None
) -> int:
    where, params = _filters(run, watermark_no)

    component_leaf_sql = f"""
        INSERT INTO aoi_hits (run_id, sample_id, event_time, definition_id)
        SELECT :run_id, gs.id, gs.event_time, ad.id
        FROM gaze_samples gs
        JOIN gaze_batches gb ON gb.id = gs.batch_id
        JOIN aoi_layout_rects alr ON alr.snapshot_id = gb.layout_snapshot_id
        JOIN aoi_definitions ad
          ON ad.aoi_set_id = :aoi_set_id
         AND ad.code = alr.semantic_code
        WHERE {where}
          AND ad.is_container = false
          AND ad.is_active = true
          AND ad.code <> 'no_label'
          AND (ad.geometry->>'anchor') IS NULL
          AND gs.viewport_x BETWEEN alr.x_min AND alr.x_max
          AND gs.viewport_y BETWEEN alr.y_min AND alr.y_max
        ON CONFLICT DO NOTHING
    """
    component_leaf = await db.execute(text(component_leaf_sql), params)

    custom_leaf_sql = f"""
        INSERT INTO aoi_hits (run_id, sample_id, event_time, definition_id)
        SELECT :run_id, gs.id, gs.event_time, ad.id
        FROM gaze_samples gs
        JOIN gaze_batches gb ON gb.id = gs.batch_id
        JOIN aoi_definitions ad
          ON ad.aoi_set_id = :aoi_set_id
         AND ad.is_container = false
         AND ad.is_active = true
         AND ad.code <> 'no_label'
         AND (ad.geometry->>'anchor') IS NOT NULL
        JOIN aoi_layout_rects anchor
          ON anchor.snapshot_id = gb.layout_snapshot_id
         AND anchor.semantic_code = ad.geometry->>'anchor'
        WHERE {where}
          AND gs.viewport_x BETWEEN
              anchor.x_min
              + (ad.geometry->>'xMin')::float * (anchor.x_max - anchor.x_min)
              AND anchor.x_min
              + (ad.geometry->>'xMax')::float * (anchor.x_max - anchor.x_min)
          AND gs.viewport_y BETWEEN
              anchor.y_min
              + (ad.geometry->>'yMin')::float * (anchor.y_max - anchor.y_min)
              AND anchor.y_min
              + (ad.geometry->>'yMax')::float * (anchor.y_max - anchor.y_min)
        ON CONFLICT DO NOTHING
    """
    custom_leaf = await db.execute(text(custom_leaf_sql), params)

    component_container_sql = f"""
        INSERT INTO aoi_hits (run_id, sample_id, event_time, definition_id)
        SELECT :run_id, gs.id, gs.event_time, ad.id
        FROM gaze_samples gs
        JOIN gaze_batches gb ON gb.id = gs.batch_id
        JOIN aoi_layout_rects alr ON alr.snapshot_id = gb.layout_snapshot_id
        JOIN aoi_definitions ad
          ON ad.aoi_set_id = :aoi_set_id
         AND ad.code = alr.semantic_code
        WHERE {where}
          AND ad.is_container = true
          AND ad.is_active = true
          AND (ad.geometry->>'anchor') IS NULL
          AND gs.viewport_x BETWEEN alr.x_min AND alr.x_max
          AND gs.viewport_y BETWEEN alr.y_min AND alr.y_max
        ON CONFLICT DO NOTHING
    """
    component_container = await db.execute(text(component_container_sql), params)

    custom_container_sql = f"""
        INSERT INTO aoi_hits (run_id, sample_id, event_time, definition_id)
        SELECT :run_id, gs.id, gs.event_time, ad.id
        FROM gaze_samples gs
        JOIN gaze_batches gb ON gb.id = gs.batch_id
        JOIN aoi_definitions ad
          ON ad.aoi_set_id = :aoi_set_id
         AND ad.is_container = true
         AND ad.is_active = true
         AND (ad.geometry->>'anchor') IS NOT NULL
        JOIN aoi_layout_rects anchor
          ON anchor.snapshot_id = gb.layout_snapshot_id
         AND anchor.semantic_code = ad.geometry->>'anchor'
        WHERE {where}
          AND gs.viewport_x BETWEEN
              anchor.x_min
              + (ad.geometry->>'xMin')::float * (anchor.x_max - anchor.x_min)
              AND anchor.x_min
              + (ad.geometry->>'xMax')::float * (anchor.x_max - anchor.x_min)
          AND gs.viewport_y BETWEEN
              anchor.y_min
              + (ad.geometry->>'yMin')::float * (anchor.y_max - anchor.y_min)
              AND anchor.y_min
              + (ad.geometry->>'yMax')::float * (anchor.y_max - anchor.y_min)
        ON CONFLICT DO NOTHING
    """
    custom_container = await db.execute(text(custom_container_sql), params)

    no_label_id = await _no_label_id(db, run.aoi_set_id)
    no_label_count = 0
    if no_label_id is not None:
        no_label_sql = f"""
            INSERT INTO aoi_hits (run_id, sample_id, event_time, definition_id)
            SELECT :run_id, gs.id, gs.event_time, :no_label_id
            FROM gaze_samples gs
            JOIN gaze_batches gb ON gb.id = gs.batch_id
            WHERE {where}
              AND gs.viewport_x BETWEEN 0 AND 1
              AND gs.viewport_y BETWEEN 0 AND 1
              AND NOT EXISTS (
                  SELECT 1
                  FROM aoi_hits ah
                  JOIN aoi_definitions ad ON ad.id = ah.definition_id
                  WHERE ah.run_id = :run_id
                    AND ah.sample_id = gs.id
                    AND ah.event_time = gs.event_time
                    AND ad.is_container = false
                    AND ad.is_active = true
                    AND ad.code <> 'no_label'
              )
            ON CONFLICT DO NOTHING
        """
        no_label = await db.execute(
            text(no_label_sql), {**params, "no_label_id": no_label_id}
        )
        no_label_count = no_label.rowcount or 0

    return (
        (component_leaf.rowcount or 0)
        + (custom_leaf.rowcount or 0)
        + (component_container.rowcount or 0)
        + (custom_container.rowcount or 0)
        + no_label_count
    )


async def execute_run(db: AsyncSession, run_id: str) -> AnalysisRunResultOut:
    run = await db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy analysis run")
    if run.status == "completed":
        return await get_run_result(db, run.id)
    run.status = "running"
    run.error = None
    await db.commit()

    try:
        aoi_set = await db.get(
            AoiSet,
            run.aoi_set_id,
            options=[raiseload(AoiSet.definitions)],
        )
        if aoi_set is None:
            raise RuntimeError("AOI set không còn tồn tại")
        watermark = await _watermark(db, run.session_id, run.presentation_id)
        watermark_no = watermark.batch_no if watermark else None

        await db.execute(
            text("DELETE FROM aoi_hits WHERE run_id = :run_id"), {"run_id": run.id}
        )
        if aoi_set.scope == "slide":
            inserted = await _insert_slide_hits(db, run, watermark_no)
        else:
            inserted = await _insert_ui_hits(db, run, watermark_no)

        if run.presentation_id:
            await metrics.compute_presentation_metrics(
                db,
                presentation_id=run.presentation_id,
                algorithm_version=run.algorithm_version,
                from_time=run.from_time,
                to_time=run.to_time,
                batch_watermark=run.batch_watermark,
            )
        else:
            await metrics.refresh_session_metrics(
                db,
                session_id=run.session_id,
                from_time=run.from_time,
                to_time=run.to_time,
                algorithm_version=run.algorithm_version,
                batch_watermark=run.batch_watermark,
            )
        run.status = "completed"
        run.completed_at = _now()
        await db.commit()
        await db.refresh(run)
        result = await get_run_result(db, run.id)
        result.hit_count = inserted
        return result
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        run = await db.get(AnalysisRun, run_id)
        if run is not None:
            run.status = "failed"
            run.error = str(exc)[:1000]
            await db.commit()
        raise


async def get_run_result(db: AsyncSession, run_id: str) -> AnalysisRunResultOut:
    run = await db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy analysis run")
    hit_count = int(
        (
            await db.execute(
                select(func.count()).select_from(AoiHit).where(AoiHit.run_id == run.id)
            )
        ).scalar_one()
    )
    metric_rows = (
        await db.execute(
            select(PresentationMetric)
            .join(
                ContentPresentation,
                ContentPresentation.id == PresentationMetric.presentation_id,
            )
            .where(
                ContentPresentation.session_id == run.session_id,
                PresentationMetric.algorithm_version == run.algorithm_version,
            )
            .order_by(PresentationMetric.computed_at)
        )
    ).scalars().all()
    return AnalysisRunResultOut(
        run=_run_out(run),
        hit_count=hit_count,
        metrics=[
            PresentationMetricOut(
                presentation_id=row.presentation_id,
                algorithm_version=row.algorithm_version,
                batch_watermark=row.batch_watermark,
                sample_count=row.sample_count,
                on_slide_count=row.on_slide_count,
                dwell_ms=row.dwell_ms,
                fixation_count=row.fixation_count,
                heatmap_grid=row.heatmap_grid,
                computed_at=row.computed_at,
            )
            for row in metric_rows
        ],
    )


async def _create_run(
    db: AsyncSession,
    *,
    session: LearningSession,
    presentation: ContentPresentation,
    aoi_set_id: str,
    start: datetime,
    end: datetime,
    algorithm_version: str,
    watermark_id: str | None,
    duplicate: bool,
) -> AnalysisRun | None:
    if duplicate:
        return None
    run = AnalysisRun(
        session_id=session.id,
        presentation_id=presentation.id,
        aoi_set_id=aoi_set_id,
        from_time=start,
        to_time=end,
        batch_watermark=watermark_id,
        algorithm_version=algorithm_version,
        config={},
        status="pending",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


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


async def execute_pending_runs(limit: int = 10) -> int:
    """Worker entrypoint: chạy các run pending theo thứ tự tạo.

    Mỗi vòng chỉ khóa đúng một run. `execute_run` chuyển status sang running
    và commit, giải phóng lock trước khi vòng sau chọn run kế tiếp — tránh
    việc commit của run đầu giải phóng lock của cả loạt run đã chọn.
    """
    processed = 0
    async with SessionLocal() as db:
        for _ in range(limit):
            run_id = (
                await db.execute(
                    select(AnalysisRun.id)
                    .where(AnalysisRun.status == "pending")
                    .order_by(AnalysisRun.created_at)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if run_id is None:
                break
            try:
                await execute_run(db, run_id)
            except Exception:  # noqa: BLE001
                pass
            processed += 1
        return processed


async def _manifest(db: AsyncSession, run: AnalysisRun) -> dict:
    session = await db.get(
        LearningSession,
        run.session_id,
        options=[raiseload(LearningSession.presentations)],
    )
    enrollment = (
        await db.get(
            Enrollment,
            session.enrollment_id,
            options=[raiseload(Enrollment.course)],
        )
        if session
        else None
    )
    item = (
        await db.get(CourseVersionItem, session.course_version_item_id)
        if session
        else None
    )
    version = (
        await db.get(
            CourseVersion,
            item.course_version_id,
            options=[
                raiseload(CourseVersion.modules),
                raiseload(CourseVersion.items),
            ],
        )
        if item
        else None
    )
    course = (
        await db.get(
            Course,
            version.course_id,
            options=[
                raiseload(Course.versions),
                raiseload(Course.enrollments),
                raiseload(Course.owner),
                raiseload(Course.creator),
            ],
        )
        if version
        else None
    )
    lesson = (
        await db.get(
            Lesson,
            item.lesson_id,
            options=[
                raiseload(Lesson.versions),
                raiseload(Lesson.slides),
            ],
        )
        if item
        else None
    )
    lesson_version = (
        await db.get(
            LessonVersion,
            item.lesson_version_id,
            options=[raiseload(LessonVersion.slides)],
        )
        if item
        else None
    )
    calibration = (
        await db.get(Calibration, session.calibration_id)
        if session and session.calibration_id
        else None
    )
    device = await db.get(Device, calibration.device_id) if calibration else None
    aoi_set = await db.get(
        AoiSet,
        run.aoi_set_id,
        options=[raiseload(AoiSet.definitions)],
    )
    definitions = (
        (
            await db.execute(
                select(AoiDefinition)
                .where(AoiDefinition.aoi_set_id == run.aoi_set_id)
                .order_by(AoiDefinition.code)
            )
        )
        .scalars()
        .all()
    )
    presentations = (
        (
            await db.execute(
                select(ContentPresentation)
                .where(ContentPresentation.session_id == run.session_id)
                .order_by(ContentPresentation.sequence_no)
            )
        )
        .scalars()
        .all()
    )
    layouts = (
        (
            await db.execute(
                select(AoiLayoutSnapshot)
                .join(
                    ContentPresentation,
                    ContentPresentation.id == AoiLayoutSnapshot.presentation_id,
                )
                .where(ContentPresentation.session_id == run.session_id)
                .order_by(AoiLayoutSnapshot.captured_at)
                .options(raiseload(AoiLayoutSnapshot.rects))
            )
        )
        .scalars()
        .all()
    )
    return {
        "type": "manifest",
        "runId": run.id,
        "presentationId": run.presentation_id,
        "scope": aoi_set.scope if aoi_set else None,
        "algorithmVersion": run.algorithm_version,
        "batchWatermark": run.batch_watermark,
        "fromTime": run.from_time.isoformat(),
        "toTime": run.to_time.isoformat(),
        "session": {
            "id": session.id if session else None,
            "enrollmentId": enrollment.id if enrollment else None,
            "studentId": enrollment.student_id if enrollment else None,
            "courseId": course.id if course else None,
            "courseVersionId": version.id if version else None,
            "lessonId": lesson.id if lesson else None,
            "lessonVersionId": lesson_version.id if lesson_version else None,
            "pipelineVersion": session.pipeline_version if session else None,
            "config": session.config if session else None,
            "trackingConsent": session.tracking_consent if session else None,
        },
        "calibration": {
            "id": calibration.id if calibration else None,
            "modelHash": calibration.model_hash if calibration else None,
            "modelVersion": calibration.model_version if calibration else None,
            "viewportWidthPx": calibration.viewport_width_px if calibration else None,
            "viewportHeightPx": calibration.viewport_height_px if calibration else None,
            "devicePixelRatio": calibration.device_pixel_ratio if calibration else None,
            "deviceFingerprint": device.fingerprint if device else None,
        },
        "aoiSet": {
            "id": aoi_set.id if aoi_set else None,
            "scope": aoi_set.scope if aoi_set else None,
            "revision": aoi_set.revision if aoi_set else None,
            "definitions": [
                {
                    "id": row.id,
                    "code": row.code,
                    "name": row.name,
                    "parentId": row.parent_id,
                    "geometry": row.geometry,
                    "isContainer": row.is_container,
                    "kind": row.kind,
                    "isActive": row.is_active,
                }
                for row in definitions
            ],
        },
        "presentations": [
            {
                "id": row.id,
                "lessonVersionSlideId": row.lesson_version_slide_id,
                "slideAoiSetId": row.slide_aoi_set_id,
                "surface": row.surface,
                "sequenceNo": row.sequence_no,
                "startedAt": row.started_at.isoformat(),
                "endedAt": row.ended_at.isoformat() if row.ended_at else None,
            }
            for row in presentations
        ],
        "layouts": [
            {
                "id": row.id,
                "presentationId": row.presentation_id,
                "uiAoiSetId": row.ui_aoi_set_id,
                "sequenceNo": row.sequence_no,
                "layoutGeneration": row.layout_generation,
                "capturedAt": row.captured_at.isoformat(),
                "imageTransform": row.image_transform,
            }
            for row in layouts
        ],
    }


async def export_lines(run_id: str) -> AsyncIterator[str]:
    async with SessionLocal() as db:
        run = await db.get(AnalysisRun, run_id)
        if run is None:
            yield json.dumps({"type": "error", "message": "not_found"}) + "\n"
            return
        manifest = await _manifest(db, run)
        yield json.dumps(manifest, ensure_ascii=False, default=str) + "\n"

        watermark_no = None
        if run.batch_watermark:
            watermark = await db.get(GazeBatch, run.batch_watermark)
            watermark_no = watermark.batch_no if watermark else None

        last_time: datetime | None = None
        last_id = 0
        while True:
            params: dict = {
                "run_id": run.id,
                "session_id": run.session_id,
                "from_time": run.from_time,
                "to_time": run.to_time,
            }
            keyset = ""
            if last_time is not None:
                keyset = "AND (gs.event_time, gs.id) > (:last_time, :last_id)"
                params["last_time"] = last_time
                params["last_id"] = last_id
            watermark = ""
            if watermark_no is not None:
                watermark = "AND gb.batch_no <= :watermark_no"
                params["watermark_no"] = watermark_no
            presentation = ""
            if run.presentation_id:
                presentation = "AND gb.presentation_id = :presentation_id"
                params["presentation_id"] = run.presentation_id
            sql = f"""
                SELECT
                    gs.id,
                    gs.event_time,
                    gs.sequence,
                    gs.capture_monotonic_ns,
                    gs.viewport_x,
                    gs.viewport_y,
                    gs.status,
                    gs.quality_flags,
                    gb.id AS batch_id,
                    gb.presentation_id,
                    gb.layout_snapshot_id,
                    als.image_transform,
                    (
                        SELECT array_agg(ad.code ORDER BY ad.code)
                        FROM aoi_hits ah
                        JOIN aoi_definitions ad ON ad.id = ah.definition_id
                        WHERE ah.run_id = :run_id
                          AND ah.sample_id = gs.id
                          AND ah.event_time = gs.event_time
                    ) AS aoi_codes
                FROM gaze_samples gs
                JOIN gaze_batches gb ON gb.id = gs.batch_id
                LEFT JOIN aoi_layout_snapshots als ON als.id = gb.layout_snapshot_id
                WHERE gs.session_id = :session_id
                  AND gs.event_time >= :from_time
                  AND gs.event_time < :to_time
                  {watermark}
                  {presentation}
                  {keyset}
                ORDER BY gs.event_time, gs.id
                LIMIT 1000
            """
            rows = (await db.execute(text(sql), params)).mappings().all()
            if not rows:
                break
            for row in rows:
                last_time = row["event_time"]
                last_id = row["id"]
                mapped = metrics._map_viewport_to_slide(
                    float(row["viewport_x"]),
                    float(row["viewport_y"]),
                    row["image_transform"],
                ) if row["viewport_x"] is not None and row["viewport_y"] is not None else None
                yield json.dumps(
                    {
                        "type": "sample",
                        "id": row["id"],
                        "eventTime": row["event_time"].isoformat(),
                        "sequence": row["sequence"],
                        "captureMonotonicNs": row["capture_monotonic_ns"],
                        "viewportX": row["viewport_x"],
                        "viewportY": row["viewport_y"],
                        "slideX": mapped[0] if mapped else None,
                        "slideY": mapped[1] if mapped else None,
                        "status": row["status"],
                        "qualityFlags": row["quality_flags"],
                        "batchId": row["batch_id"],
                        "presentationId": row["presentation_id"],
                        "layoutSnapshotId": row["layout_snapshot_id"],
                        "aoiCodes": row["aoi_codes"] or [],
                    },
                    ensure_ascii=False,
                    default=str,
                ) + "\n"
        yield json.dumps({"type": "end", "runId": run.id}) + "\n"
