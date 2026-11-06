"""Analysis runs: run-scoped AOI hits + presentation metrics + streaming export."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

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
    AnalysisRunCreateIn,
    AnalysisRunOut,
    AnalysisRunResultOut,
    PresentationMetricOut,
)
from app.services import metrics

ALGORITHM_VERSION = "gaze-metrics-v1"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _run_out(row: AnalysisRun) -> AnalysisRunOut:
    return AnalysisRunOut(
        id=row.id,
        session_id=row.session_id,
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


async def _session_course(
    db: AsyncSession, session_id: str
) -> tuple[LearningSession, Course, CourseVersionItem]:
    session = await db.get(LearningSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên học")
    item = await db.get(CourseVersionItem, session.course_version_item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nội dung phiên")
    version = await db.get(CourseVersion, item.course_version_id)
    course = await db.get(Course, version.course_id) if version else None
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    return session, course, item


async def _watermark(db: AsyncSession, session_id: str) -> GazeBatch | None:
    return (
        await db.execute(
            select(GazeBatch)
            .where(GazeBatch.session_id == session_id)
            .order_by(GazeBatch.batch_no.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def create_run(
    db: AsyncSession, user: User, body: AnalysisRunCreateIn
) -> AnalysisRun:
    session, course, item = await _session_course(db, body.session_id)
    if not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    aoi_set = await db.get(AoiSet, body.aoi_set_id)
    if aoi_set is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bộ AOI")
    if aoi_set.state != "published":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "aoi_not_published", "message": "Bộ AOI chưa publish"},
        )
    if aoi_set.scope == "slide":
        # Trigger DB kiểm tra slide thuộc lesson version; kiểm tra sớm để trả 400 rõ ràng.
        slide_version_id = aoi_set.slide_version_id
        membership = (
            await db.execute(
                select(LessonVersionSlide).where(
                    LessonVersionSlide.lesson_version_id == item.lesson_version_id,
                    LessonVersionSlide.slide_version_id == slide_version_id,
                )
            )
        ).scalar_one_or_none()
        if membership is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Bộ AOI slide không thuộc bài học của phiên",
            )
    watermark = await _watermark(db, session.id)
    run = AnalysisRun(
        session_id=session.id,
        aoi_set_id=aoi_set.id,
        from_time=body.from_time,
        to_time=body.to_time,
        batch_watermark=watermark.id if watermark else None,
        algorithm_version=body.algorithm_version or ALGORITHM_VERSION,
        config=body.config,
        status="pending",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def _insert_slide_hits(
    db: AsyncSession, run: AnalysisRun, watermark_no: int | None
) -> int:
    conditions = [
        "gs.session_id = :session_id",
        "gs.event_time >= :from_time",
        "gs.event_time < :to_time",
        "gs.status = 'ok'",
        "gs.viewport_x IS NOT NULL",
        "gs.viewport_y IS NOT NULL",
        "ad.aoi_set_id = :aoi_set_id",
    ]
    params: dict = {
        "session_id": run.session_id,
        "from_time": run.from_time,
        "to_time": run.to_time,
        "aoi_set_id": run.aoi_set_id,
        "run_id": run.id,
    }
    if watermark_no is not None:
        conditions.append("gb.batch_no <= :watermark_no")
        params["watermark_no"] = watermark_no
    sql = f"""
        INSERT INTO aoi_hits (run_id, sample_id, event_time, definition_id)
        SELECT :run_id, gs.id, gs.event_time, ad.id
        FROM gaze_samples gs
        JOIN gaze_batches gb ON gb.id = gs.batch_id
        LEFT JOIN aoi_layout_snapshots als ON als.id = gb.layout_snapshot_id
        JOIN aoi_definitions ad ON ad.aoi_set_id = :aoi_set_id
        WHERE {' AND '.join(conditions)}
          AND (
              (gs.viewport_x - COALESCE((als.image_transform->>'left')::float, 0))
              / NULLIF(COALESCE((als.image_transform->>'width')::float, 1), 0)
          ) BETWEEN (ad.geometry->>'xMin')::float AND (ad.geometry->>'xMax')::float
          AND (
              (gs.viewport_y - COALESCE((als.image_transform->>'top')::float, 0))
              / NULLIF(COALESCE((als.image_transform->>'height')::float, 1), 0)
          ) BETWEEN (ad.geometry->>'yMin')::float AND (ad.geometry->>'yMax')::float
        ON CONFLICT DO NOTHING
    """
    result = await db.execute(text(sql), params)
    return result.rowcount or 0


async def _insert_ui_hits(
    db: AsyncSession, run: AnalysisRun, watermark_no: int | None
) -> int:
    conditions = [
        "gs.session_id = :session_id",
        "gs.event_time >= :from_time",
        "gs.event_time < :to_time",
        "gs.status = 'ok'",
        "gs.viewport_x IS NOT NULL",
        "gs.viewport_y IS NOT NULL",
        "ad.aoi_set_id = :aoi_set_id",
    ]
    params: dict = {
        "session_id": run.session_id,
        "from_time": run.from_time,
        "to_time": run.to_time,
        "aoi_set_id": run.aoi_set_id,
        "run_id": run.id,
    }
    if watermark_no is not None:
        conditions.append("gb.batch_no <= :watermark_no")
        params["watermark_no"] = watermark_no
    sql = f"""
        INSERT INTO aoi_hits (run_id, sample_id, event_time, definition_id)
        SELECT :run_id, gs.id, gs.event_time, ad.id
        FROM gaze_samples gs
        JOIN gaze_batches gb ON gb.id = gs.batch_id
        JOIN aoi_layout_rects alr ON alr.snapshot_id = gb.layout_snapshot_id
        JOIN aoi_definitions ad
          ON ad.aoi_set_id = :aoi_set_id AND ad.code = alr.semantic_code
        WHERE {' AND '.join(conditions)}
          AND gs.viewport_x BETWEEN alr.x_min AND alr.x_max
          AND gs.viewport_y BETWEEN alr.y_min AND alr.y_max
        ON CONFLICT DO NOTHING
    """
    result = await db.execute(text(sql), params)
    return result.rowcount or 0


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
        aoi_set = await db.get(AoiSet, run.aoi_set_id)
        if aoi_set is None:
            raise RuntimeError("AOI set không còn tồn tại")
        watermark_no = None
        if run.batch_watermark:
            watermark = await db.get(GazeBatch, run.batch_watermark)
            watermark_no = watermark.batch_no if watermark else None

        await db.execute(
            text("DELETE FROM aoi_hits WHERE run_id = :run_id"), {"run_id": run.id}
        )
        if aoi_set.scope == "slide":
            inserted = await _insert_slide_hits(db, run, watermark_no)
        else:
            inserted = await _insert_ui_hits(db, run, watermark_no)

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


async def list_runs(
    db: AsyncSession, user: User, *, session_id: str | None = None
) -> list[AnalysisRunOut]:
    stmt = select(AnalysisRun).order_by(AnalysisRun.created_at.desc())
    if session_id:
        stmt = stmt.where(AnalysisRun.session_id == session_id)
    rows = (await db.execute(stmt)).scalars().all()
    out: list[AnalysisRunOut] = []
    for row in rows:
        try:
            _, course, _ = await _session_course(db, row.session_id)
        except HTTPException:
            continue
        if await can_access_course(db, course, user):
            out.append(_run_out(row))
    return out


async def rebuild_course(
    db: AsyncSession,
    user: User,
    *,
    course_id: str,
    from_time: datetime | None,
    to_time: datetime | None,
    algorithm_version: str,
) -> tuple[int, int, int]:
    course = await db.get(Course, course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    if not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    if course.published_version_id is None:
        return 0, 0, 0
    version = await db.get(CourseVersion, course.published_version_id)
    if version is None:
        return 0, 0, 0
    items = (
        await db.execute(
            select(CourseVersionItem).where(
                CourseVersionItem.course_version_id == version.id
            )
        )
    ).scalars().all()
    runs = 0
    completed = 0
    failed = 0
    for item in items:
        sessions = (
            await db.execute(
                select(LearningSession).where(
                    LearningSession.course_version_item_id == item.id
                )
            )
        ).scalars().all()
        for session in sessions:
            start = from_time or session.started_at
            end = to_time or session.ended_at or _now()
            if end <= start:
                continue
            aoi_set = await _published_set_for_session(db, session, item)
            if aoi_set is None:
                continue
            watermark = await _watermark(db, session.id)
            run = AnalysisRun(
                session_id=session.id,
                aoi_set_id=aoi_set.id,
                from_time=start,
                to_time=end,
                batch_watermark=watermark.id if watermark else None,
                algorithm_version=algorithm_version,
                config={},
                status="pending",
            )
            db.add(run)
            await db.commit()
            await db.refresh(run)
            runs += 1
            try:
                await execute_run(db, run.id)
                completed += 1
            except Exception:  # noqa: BLE001
                failed += 1
    return runs, completed, failed


async def _published_set_for_session(
    db: AsyncSession, session: LearningSession, item: CourseVersionItem
) -> AoiSet | None:
    slide = (
        await db.execute(
            select(LessonVersionSlide)
            .where(LessonVersionSlide.lesson_version_id == item.lesson_version_id)
            .order_by(LessonVersionSlide.position)
            .limit(1)
        )
    ).scalar_one_or_none()
    if slide is not None:
        row = (
            await db.execute(
                select(AoiSet).where(
                    AoiSet.scope == "slide",
                    AoiSet.slide_version_id == slide.slide_version_id,
                    AoiSet.state == "published",
                )
            )
        ).scalar_one_or_none()
        if row is not None:
            return row
    return (
        await db.execute(
            select(AoiSet).where(
                AoiSet.scope == "ui",
                AoiSet.ui_schema_version == "reader-v1",
                AoiSet.state == "published",
            )
        )
    ).scalar_one_or_none()


async def execute_pending_runs(limit: int = 10) -> int:
    """Worker entrypoint: chạy các run pending theo thứ tự tạo."""
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(AnalysisRun.id)
                .where(AnalysisRun.status == "pending")
                .order_by(AnalysisRun.created_at)
                .limit(limit)
            )
        ).scalars().all()
        for run_id in rows:
            try:
                await execute_run(db, run_id)
            except Exception:  # noqa: BLE001
                continue
        return len(rows)


async def _manifest(db: AsyncSession, run: AnalysisRun) -> dict:
    session = await db.get(LearningSession, run.session_id)
    enrollment = await db.get(Enrollment, session.enrollment_id) if session else None
    item = (
        await db.get(CourseVersionItem, session.course_version_item_id)
        if session
        else None
    )
    version = await db.get(CourseVersion, item.course_version_id) if item else None
    course = await db.get(Course, version.course_id) if version else None
    lesson = await db.get(Lesson, item.lesson_id) if item else None
    lesson_version = (
        await db.get(LessonVersion, item.lesson_version_id) if item else None
    )
    calibration = (
        await db.get(Calibration, session.calibration_id)
        if session and session.calibration_id
        else None
    )
    device = await db.get(Device, calibration.device_id) if calibration else None
    aoi_set = await db.get(AoiSet, run.aoi_set_id)
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
            )
        )
        .scalars()
        .all()
    )
    return {
        "type": "manifest",
        "runId": run.id,
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
            "maePx": calibration.mae_px if calibration else None,
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
                }
                for row in definitions
            ],
        },
        "presentations": [
            {
                "id": row.id,
                "lessonVersionSlideId": row.lesson_version_slide_id,
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
