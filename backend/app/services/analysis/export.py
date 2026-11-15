"""Streaming JSONL export cho một lesson."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime

from sqlalchemy import text

from app.db.session import SessionLocal

SAMPLE_SQL = """
SELECT
    gs.id,
    gs.event_time,
    gs.sequence,
    gs.client_batch_id,
    gs.viewport_x,
    gs.viewport_y,
    gs.slide_x,
    gs.slide_y,
    gs.aoi_label,
    gs.aoi_codes,
    gs.status,
    gs.quality_flags,
    cv.id AS content_view_id,
    cv.sequence_no AS view_sequence,
    ls.tracking_consent,
    ls.id AS session_id,
    ls.enrollment_id,
    l.id AS lesson_id,
    l.title AS lesson_title,
    s.id AS slide_id,
    s.title AS slide_title,
    s.page_number
FROM gaze_samples gs
JOIN content_views cv ON cv.id = gs.content_view_id
JOIN learning_sessions ls ON ls.id = cv.session_id
JOIN lessons l ON l.id = ls.lesson_id
LEFT JOIN slides s ON s.id = cv.slide_id
WHERE ls.lesson_id = :lesson_id
ORDER BY gs.event_time, gs.id
LIMIT 1000
"""

SAMPLE_AFTER_SQL = SAMPLE_SQL.replace(
    "WHERE ls.lesson_id = :lesson_id",
    "WHERE ls.lesson_id = :lesson_id "
    "AND (gs.event_time, gs.id) > "
    "(CAST(:after_time AS TIMESTAMPTZ), CAST(:after_id AS BIGINT))",
)


async def export_lines(
    lesson_id: str, scope: str | None = None
) -> AsyncIterator[str]:
    async with SessionLocal() as db:
        lesson = (
            await db.execute(
                text(
                    """
                    SELECT l.id, l.title, l.kind, m.id AS module_id,
                           m.title AS module_title, c.id AS course_id,
                           c.title AS course_title
                    FROM lessons l
                    JOIN course_modules m ON m.id = l.module_id
                    JOIN courses c ON c.id = m.course_id
                    WHERE l.id = :lesson_id
                    """
                ),
                {"lesson_id": lesson_id},
            )
        ).mappings().one_or_none()
        if lesson is None:
            yield json.dumps({"type": "error", "message": "not_found"}) + "\n"
            return

        slides = (
            await db.execute(
                text(
                    """
                    SELECT id, position, page_number, title
                    FROM slides WHERE lesson_id = :lesson_id
                    ORDER BY position
                    """
                ),
                {"lesson_id": lesson_id},
            )
        ).mappings().all()
        aois = (
            await db.execute(
                text(
                    """
                    SELECT a.id, a.slide_id, a.code, a.name, a.label, a.kind,
                           a.is_container, a.is_active, a.geometry
                    FROM aois a
                    JOIN slides s ON s.id = a.slide_id
                    WHERE s.lesson_id = :lesson_id
                    ORDER BY a.code
                    """
                ),
                {"lesson_id": lesson_id},
            )
        ).mappings().all()
        yield json.dumps(
            {
                "type": "manifest",
                "schemaVersion": 10,
                "aoiLabelVersion": "surface-v1",
                "course": {
                    "id": str(lesson["course_id"]),
                    "title": lesson["course_title"],
                },
                "module": {
                    "id": str(lesson["module_id"]),
                    "title": lesson["module_title"],
                },
                "lesson": {
                    "id": str(lesson["id"]),
                    "title": lesson["title"],
                    "kind": lesson["kind"],
                },
                "slides": [
                    {
                        "id": str(row["id"]),
                        "position": row["position"],
                        "pageNumber": row["page_number"],
                        "title": row["title"],
                    }
                    for row in slides
                ],
                "aois": [
                    {
                        "id": str(row["id"]),
                        "slideId": str(row["slide_id"]),
                        "code": row["code"],
                        "name": row["name"],
                        "label": row["label"],
                        "kind": row["kind"],
                        "isContainer": row["is_container"],
                        "isActive": row["is_active"],
                        "geometry": row["geometry"],
                    }
                    for row in aois
                ],
            },
            ensure_ascii=False,
            default=str,
        ) + "\n"

        last_time: datetime | None = None
        last_id = 0
        while True:
            if last_time is None:
                rows = (
                    await db.execute(
                        text(SAMPLE_SQL), {"lesson_id": lesson_id}
                    )
                ).mappings().all()
            else:
                rows = (
                    await db.execute(
                        text(SAMPLE_AFTER_SQL),
                        {
                            "lesson_id": lesson_id,
                            "after_time": last_time,
                            "after_id": last_id,
                        },
                    )
                ).mappings().all()
            if not rows:
                break
            for row in rows:
                last_time = row["event_time"]
                last_id = row["id"]
                label = row["aoi_label"]
                filtered_out = bool(
                    scope == "slide"
                    and label
                    and not label.startswith("SLIDE_")
                ) or bool(
                    scope == "ui"
                    and label
                    and label.startswith("SLIDE_")
                )
                if filtered_out:
                    label = None
                    codes = []
                else:
                    codes = [label] if label else list(row["aoi_codes"] or [])
                    if scope == "slide":
                        codes = [
                            code
                            for code in codes
                            if code.startswith("SLIDE_")
                            or (label is None and not code.startswith("ui:"))
                        ]
                    elif scope == "ui":
                        codes = [
                            code
                            for code in codes
                            if (
                                label is not None
                                and not code.startswith("SLIDE_")
                            )
                            or (label is None and code.startswith("ui:"))
                        ]
                yield json.dumps(
                    {
                        "type": "sample",
                        "id": row["id"],
                        "eventTime": row["event_time"].isoformat(),
                        "sequence": row["sequence"],
                        "batchId": str(row["client_batch_id"]),
                        "contentViewId": str(row["content_view_id"]),
                        "viewSequence": row["view_sequence"],
                        "sessionId": str(row["session_id"]),
                        "enrollmentId": str(row["enrollment_id"]),
                        "lessonId": str(row["lesson_id"]),
                        "lessonTitle": row["lesson_title"],
                        "slideId": str(row["slide_id"]) if row["slide_id"] else None,
                        "slideTitle": row["slide_title"],
                        "pageNumber": row["page_number"],
                        "viewportX": row["viewport_x"],
                        "viewportY": row["viewport_y"],
                        "slideX": row["slide_x"],
                        "slideY": row["slide_y"],
                        "aoiLabel": label,
                        "aoiCodes": codes,
                        "status": row["status"],
                        "trackingConsent": row["tracking_consent"],
                        "qualityFlags": row["quality_flags"],
                    },
                    ensure_ascii=False,
                    default=str,
                ) + "\n"
        yield json.dumps({"type": "end", "lessonId": lesson_id}) + "\n"


VISIT_SAMPLE_SQL = """
SELECT
    gs.id,
    gs.event_time,
    gs.sequence,
    gs.client_batch_id,
    gs.viewport_x,
    gs.viewport_y,
    gs.original_viewport_x,
    gs.original_viewport_y,
    gs.slide_x,
    gs.slide_y,
    gs.aoi_label,
    gs.aoi_codes,
    gs.status,
    gs.quality_flags,
    cv.id AS content_view_id,
    cv.sequence_no AS view_sequence,
    ls.id AS session_id,
    ls.enrollment_id,
    l.id AS lesson_id,
    l.title AS lesson_title,
    s.id AS slide_id,
    s.title AS slide_title,
    s.page_number,
    e.student_id,
    u.full_name AS student_name,
    u.email AS student_email,
    sp.student_code,
    c.id AS course_id,
    c.title AS course_title,
    v.id AS visit_id,
    v.started_at AS visit_started_at
FROM gaze_samples gs
JOIN content_views cv ON cv.id = gs.content_view_id
JOIN learning_sessions ls ON ls.id = cv.session_id
JOIN course_visits v ON v.id = ls.course_visit_id
JOIN enrollments e ON e.id = ls.enrollment_id
JOIN users u ON u.id = e.student_id
LEFT JOIN student_profiles sp ON sp.user_id = u.id
JOIN courses c ON c.id = e.course_id
JOIN lessons l ON l.id = ls.lesson_id
LEFT JOIN slides s ON s.id = cv.slide_id
WHERE v.id = :visit_id
ORDER BY gs.event_time, gs.id
LIMIT 1000
"""

VISIT_SAMPLE_AFTER_SQL = VISIT_SAMPLE_SQL.replace(
    "WHERE v.id = :visit_id",
    "WHERE v.id = :visit_id "
    "AND (gs.event_time, gs.id) > "
    "(CAST(:after_time AS TIMESTAMPTZ), CAST(:after_id AS BIGINT))",
)


async def export_visit_lines(visit_id: str) -> AsyncIterator[str]:
    async with SessionLocal() as db:
        visit = (
            await db.execute(
                text(
                    """
                    SELECT v.id, v.started_at, v.ended_at, v.status,
                           e.student_id, e.course_id,
                           u.full_name, u.email, sp.student_code,
                           c.title AS course_title
                    FROM course_visits v
                    JOIN enrollments e ON e.id = v.enrollment_id
                    JOIN users u ON u.id = e.student_id
                    LEFT JOIN student_profiles sp ON sp.user_id = u.id
                    JOIN courses c ON c.id = e.course_id
                    WHERE v.id = :visit_id
                    """
                ),
                {"visit_id": visit_id},
            )
        ).mappings().one_or_none()
        if visit is None:
            yield json.dumps({"type": "error", "message": "not_found"}) + "\n"
            return

        yield json.dumps(
            {
                "type": "manifest",
                "schemaVersion": 11,
                "aoiLabelVersion": "surface-v1",
                "visit": {
                    "id": str(visit["id"]),
                    "startedAt": visit["started_at"].isoformat(),
                    "endedAt": visit["ended_at"].isoformat()
                    if visit["ended_at"]
                    else None,
                    "status": visit["status"],
                },
                "student": {
                    "id": str(visit["student_id"]),
                    "name": visit["full_name"] or visit["email"],
                    "code": visit["student_code"] or "",
                    "email": visit["email"],
                },
                "course": {
                    "id": str(visit["course_id"]),
                    "title": visit["course_title"],
                },
            },
            ensure_ascii=False,
            default=str,
        ) + "\n"

        last_time: datetime | None = None
        last_id = 0
        while True:
            if last_time is None:
                rows = (
                    await db.execute(
                        text(VISIT_SAMPLE_SQL), {"visit_id": visit_id}
                    )
                ).mappings().all()
            else:
                rows = (
                    await db.execute(
                        text(VISIT_SAMPLE_AFTER_SQL),
                        {
                            "visit_id": visit_id,
                            "after_time": last_time,
                            "after_id": last_id,
                        },
                    )
                ).mappings().all()
            if not rows:
                break
            for row in rows:
                last_time = row["event_time"]
                last_id = row["id"]
                yield json.dumps(
                    {
                        "type": "sample",
                        "id": row["id"],
                        "eventTime": row["event_time"].isoformat(),
                        "sequence": row["sequence"],
                        "batchId": str(row["client_batch_id"]),
                        "visitId": str(row["visit_id"]),
                        "studentId": str(row["student_id"]),
                        "studentName": row["student_name"] or row["student_email"],
                        "studentCode": row["student_code"] or "",
                        "courseId": str(row["course_id"]),
                        "contentViewId": str(row["content_view_id"]),
                        "viewSequence": row["view_sequence"],
                        "sessionId": str(row["session_id"]),
                        "enrollmentId": str(row["enrollment_id"]),
                        "lessonId": str(row["lesson_id"]),
                        "lessonTitle": row["lesson_title"],
                        "slideId": str(row["slide_id"]) if row["slide_id"] else None,
                        "slideTitle": row["slide_title"],
                        "pageNumber": row["page_number"],
                        "viewportX": row["viewport_x"],
                        "viewportY": row["viewport_y"],
                        "originalViewportX": row["original_viewport_x"],
                        "originalViewportY": row["original_viewport_y"],
                        "slideX": row["slide_x"],
                        "slideY": row["slide_y"],
                        "aoiLabel": row["aoi_label"],
                        "aoiCodes": row["aoi_codes"] or [],
                        "status": row["status"],
                        "qualityFlags": row["quality_flags"],
                    },
                    ensure_ascii=False,
                    default=str,
                ) + "\n"
        yield json.dumps({"type": "end", "visitId": visit_id}) + "\n"
