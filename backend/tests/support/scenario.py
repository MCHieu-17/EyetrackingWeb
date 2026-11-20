"""Dựng kịch bản gaze đầy đủ qua API + worker, dùng cho analytics/metrics."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from tests.conftest import (
    create_course,
    create_lesson,
    create_slide,
    create_user,
    login,
)
from tests.support.workers import run_analysis

SESSION_BODY = {
    "deviceFingerprint": "analytics-device",
    "viewportWidthPx": 1280,
    "viewportHeightPx": 720,
    "calibrationWidthPx": 1280,
    "calibrationHeightPx": 720,
    "devicePixelRatio": 1.0,
    "trackingConsent": True,
}


async def build_lesson_gaze(
    *,
    teacher_client: AsyncClient,
    student_client: AsyncClient,
    with_layout: bool = True,
    with_slide_aois: bool = True,
) -> dict:
    teacher = await create_user(role="teacher", email=f"t-scn-{uuid.uuid4().hex[:8]}@example.com")
    student = await create_user(email=f"s-scn-{uuid.uuid4().hex[:8]}@example.com")
    ids = await create_course(
        teacher_id=teacher["id"],
        student_id=student["id"],
        status="published",
        require_calibration=False,
    )
    lesson_id = await create_lesson(module_id=ids["module_id"])
    slide_id = await create_slide(lesson_id=lesson_id)

    await login(teacher_client, teacher["email"])
    if with_slide_aois:
        response = await teacher_client.put(
            f"/api/aois/slides/{slide_id}",
            json={
                "definitions": [
                    {
                        "code": "custom_a",
                        "name": "Vùng custom",
                        "label": "AOI_CUSTOM",
                        "geometry": {
                            "xMin": 0.1,
                            "yMin": 0.1,
                            "xMax": 0.5,
                            "yMax": 0.5,
                        },
                        "kind": "custom",
                    },
                    {
                        "code": "text_b",
                        "name": "Vùng text",
                        "label": "AOI_TEXT",
                        "geometry": {
                            "xMin": 0.0,
                            "yMin": 0.0,
                            "xMax": 0.7,
                            "yMax": 0.7,
                        },
                        "kind": "text",
                    },
                    {
                        "code": "text_c",
                        "name": "Vùng text 2",
                        "label": "AOI_TEXT2",
                        "geometry": {
                            "xMin": 0.6,
                            "yMin": 0.6,
                            "xMax": 0.9,
                            "yMax": 0.9,
                        },
                        "kind": "text",
                    },
                ]
            },
        )
        assert response.status_code == 200, response.text

    ui = await teacher_client.put(
        "/api/aois/ui/reader-v1",
        json={
            "definitions": [
                {
                    "code": "header",
                    "name": "Header",
                    "geometry": {"selector": "[data-aoi='header']"},
                    "kind": "ui",
                }
            ]
        },
    )
    assert ui.status_code == 200, ui.text

    await login(student_client, student["email"])
    visit = await student_client.post(
        "/api/course-visits", json={"enrollmentId": ids["enrollment_id"]}
    )
    assert visit.status_code == 201, visit.text
    session = await student_client.post(
        "/api/learning-sessions",
        json={
            **SESSION_BODY,
            "enrollmentId": ids["enrollment_id"],
            "lessonId": lesson_id,
            "courseVisitId": visit.json()["id"],
        },
    )
    assert session.status_code == 201, session.text
    session_id = session.json()["id"]

    presentation = await student_client.post(
        f"/api/learning-sessions/{session_id}/presentations",
        json={
            "surface": "lesson",
            "slideId": slide_id,
            "clientPresentationId": str(uuid.uuid4()),
        },
    )
    assert presentation.status_code == 201, presentation.text
    presentation_id = presentation.json()["id"]

    layout_id = None
    if with_layout:
        layout = await student_client.post(
            f"/api/presentations/{presentation_id}/layouts",
            json={
                "sequenceNo": 0,
                "layoutGeneration": 1,
                "imageTransform": {
                    "left": 0.1,
                    "top": 0.1,
                    "width": 0.8,
                    "height": 0.8,
                },
                "rects": [
                    {
                        "code": "header",
                        "elementKey": "header",
                        "xMin": 0.9,
                        "yMin": 0.9,
                        "xMax": 1.0,
                        "yMax": 1.0,
                    }
                ],
            },
        )
        assert layout.status_code == 201, layout.text
        layout_id = layout.json()["id"]

    base = datetime.now(UTC)
    samples = [
        {
            "sequence": 0,
            "eventTime": base.isoformat(),
            "viewportX": 0.26,
            "viewportY": 0.26,
            "status": "ok",
            "qualityFlags": {},
        },
        {
            "sequence": 1,
            "eventTime": (base + timedelta(milliseconds=100)).isoformat(),
            "viewportX": 0.62,
            "viewportY": 0.62,
            "status": "ok",
            "qualityFlags": {},
        },
        {
            "sequence": 2,
            "eventTime": (base + timedelta(milliseconds=200)).isoformat(),
            "viewportX": 0.95,
            "viewportY": 0.95,
            "status": "ok",
            "qualityFlags": {},
        },
    ]
    batch = await student_client.post(
        f"/api/learning-sessions/{session_id}/gaze-batches",
        json={
            "batchId": str(uuid.uuid4()),
            "presentationId": presentation_id,
            "layoutId": layout_id,
            "sequenceStart": 0,
            "sequenceEnd": 2,
            "samples": samples,
        },
    )
    assert batch.status_code == 200, batch.text

    ended = await student_client.patch(
        f"/api/learning-sessions/{session_id}", json={"status": "completed"}
    )
    assert ended.status_code == 200, ended.text
    await run_analysis()
    return {
        "teacher": teacher,
        "student": student,
        "ids": ids,
        "lesson_id": lesson_id,
        "slide_id": slide_id,
        "session_id": session_id,
        "presentation_id": presentation_id,
        "layout_id": layout_id,
        "visit_id": visit.json()["id"],
    }
