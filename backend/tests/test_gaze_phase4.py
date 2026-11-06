"""Phase 4 smoke: presentation → layout → idempotent gaze batch."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import uuid
from datetime import datetime, timezone

import pymupdf
import pytest

from tests.conftest import auth, login, make_user


def _pdf_bytes() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Gaze slide")
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture()
def teacher(client):
    asyncio.run(make_user("teacher5@example.com", "teacher", full_name="GV Phase 4"))
    return login(client, "teacher5@example.com")


@pytest.fixture()
def student(client):
    asyncio.run(make_user("student5@example.com", "student", full_name="SV Phase 4"))
    return login(client, "student5@example.com")


def _setup_session(client, teacher, student):
    headers = auth(teacher)
    course = client.post(
        "/teacher/courses", json={"title": "Khóa Gaze"}, headers=headers
    ).json()
    module = client.post(
        f"/teacher/courses/{course['id']}/modules",
        json={"title": "Chương"},
        headers=headers,
    ).json()
    lesson = client.post(
        f"/teacher/modules/{module['id']}/lessons",
        json={"title": "Bài"},
        headers=headers,
    ).json()
    upload = client.post(
        f"/teacher/lessons/{lesson['id']}/slides/upload",
        files={"pdf": ("gaze.pdf", _pdf_bytes(), "application/pdf")},
        headers=headers,
    )
    assert upload.status_code == 201, upload.text
    published = client.post(
        f"/teacher/courses/{course['id']}/publish", json={}, headers=headers
    )
    assert published.status_code == 200, published.text

    student_headers = auth(student)
    enroll = client.post(f"/api/courses/{course['id']}/enroll", headers=student_headers)
    enrollment_id = enroll.json()["enrollmentId"]
    fingerprint = "device-phase4"
    calibration = client.post(
        "/api/calibrations",
        json={
            "deviceFingerprint": fingerprint,
            "numPoints": 16,
            "modelUbjBase64": base64.b64encode(b"fake-model").decode(),
            "viewportWidthPx": 1280,
            "viewportHeightPx": 720,
            "devicePixelRatio": 1,
        },
        headers=student_headers,
    )
    assert calibration.status_code == 201, calibration.text
    session = client.post(
        "/api/learning-sessions",
        json={
            "enrollmentId": enrollment_id,
            "lessonId": lesson["id"],
            "deviceFingerprint": fingerprint,
            "viewportWidthPx": 1280,
            "viewportHeightPx": 720,
            "calibrationWidthPx": 1280,
            "calibrationHeightPx": 720,
            "devicePixelRatio": 1,
            "trackingConsent": True,
        },
        headers=student_headers,
    )
    assert session.status_code == 201, session.text
    session_id = session.json()["id"]
    contents = client.get(
        f"/api/learning-sessions/{session_id}/contents", headers=student_headers
    )
    slide_id = contents.json()[0]["id"]
    return student_headers, session_id, slide_id


def test_gaze_batch_idempotency_and_validation(client, teacher, student):
    headers, session_id, slide_id = _setup_session(client, teacher, student)

    presentation = client.post(
        f"/api/learning-sessions/{session_id}/presentations",
        json={
            "lessonVersionSlideId": slide_id,
            "surface": "lesson",
            "sequenceNo": 0,
        },
        headers=headers,
    )
    assert presentation.status_code == 201, presentation.text
    presentation_id = presentation.json()["id"]

    layout = client.post(
        f"/api/presentations/{presentation_id}/layouts",
        json={
            "sequenceNo": 0,
            "layoutGeneration": 0,
            "imageTransform": {"left": 0, "top": 0, "width": 1280, "height": 720},
            "rects": [
                {
                    "semanticCode": "slide",
                    "elementKey": "slide",
                    "xMin": 0,
                    "yMin": 0,
                    "xMax": 1,
                    "yMax": 1,
                }
            ],
        },
        headers=headers,
    )
    assert layout.status_code == 201, layout.text
    layout_id = layout.json()["id"]

    now = datetime.now(timezone.utc).isoformat()
    samples = [
        {
            "sequence": 0,
            "captureMonotonicNs": 1000,
            "eventTime": now,
            "viewportX": 0.4,
            "viewportY": 0.5,
            "status": "ok",
            "qualityFlags": {},
        },
        {
            "sequence": 1,
            "captureMonotonicNs": 2000,
            "eventTime": now,
            "viewportX": None,
            "viewportY": None,
            "status": "no_face",
            "qualityFlags": {},
        },
    ]
    payload_hash = hashlib.sha256(
        json.dumps(samples, sort_keys=True).encode()
    ).hexdigest()
    batch_id = str(uuid.uuid4())
    body = {
        "batchId": batch_id,
        "batchNo": 0,
        "presentationId": presentation_id,
        "layoutSnapshotId": layout_id,
        "sequenceStart": 0,
        "sequenceEnd": 1,
        "payloadHash": payload_hash,
        "samples": samples,
    }
    ack = client.post(
        f"/api/learning-sessions/{session_id}/gaze-batches",
        json=body,
        headers=headers,
    )
    assert ack.status_code == 200, ack.text
    assert ack.json()["stored"] == 2

    duplicate = client.post(
        f"/api/learning-sessions/{session_id}/gaze-batches",
        json=body,
        headers=headers,
    )
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["duplicate"] == 2
    assert duplicate.json()["stored"] == 0

    conflict = client.post(
        f"/api/learning-sessions/{session_id}/gaze-batches",
        json={**body, "payloadHash": "0" * 64},
        headers=headers,
    )
    assert conflict.status_code == 409

    out_of_order = client.post(
        f"/api/learning-sessions/{session_id}/gaze-batches",
        json={
            **body,
            "batchId": str(uuid.uuid4()),
            "batchNo": 5,
            "payloadHash": "1" * 64,
        },
        headers=headers,
    )
    assert out_of_order.status_code == 409

    invalid = client.post(
        f"/api/learning-sessions/{session_id}/gaze-batches",
        json={
            **body,
            "batchId": str(uuid.uuid4()),
            "batchNo": 1,
            "payloadHash": "2" * 64,
            "samples": [
                {
                    "sequence": 2,
                    "captureMonotonicNs": 3000,
                    "eventTime": now,
                    "viewportX": None,
                    "viewportY": None,
                    "status": "ok",
                    "qualityFlags": {},
                }
            ],
            "sequenceStart": 2,
            "sequenceEnd": 2,
        },
        headers=headers,
    )
    assert invalid.status_code == 422
