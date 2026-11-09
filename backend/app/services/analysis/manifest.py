"""Manifest cho streaming export."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload

from app.models.aoi import AnalysisRun, AoiDefinition, AoiLayoutSnapshot, AoiSet
from app.models.calibration import Calibration, Device
from app.models.course import (
    Course,
    CourseVersion,
    CourseVersionItem,
    Enrollment,
    Lesson,
    LessonVersion,
)
from app.models.gaze import ContentPresentation, LearningSession


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
