"""Phase 5: versioned AOI, analysis runs, metrics, heatmap, export."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

import pymupdf
import pytest

from tests.conftest import auth, login, make_user


def _pdf_bytes() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "AOI slide")
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture()
def teacher(client):
    asyncio.run(make_user("teacher-aoi@example.com", "teacher", full_name="GV AOI"))
    return login(client, "teacher-aoi@example.com")


@pytest.fixture()
def student(client):
    asyncio.run(make_user("student-aoi@example.com", "student", full_name="SV AOI"))
    return login(client, "student-aoi@example.com")


def _setup(client, teacher, student):
    headers = auth(teacher)
    course = client.post(
        "/teacher/courses", json={"title": "Khóa AOI"}, headers=headers
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
        files={"pdf": ("aoi.pdf", _pdf_bytes(), "application/pdf")},
        headers=headers,
    )
    assert upload.status_code == 201, upload.text
    published = client.post(
        f"/teacher/courses/{course['id']}/publish", json={}, headers=headers
    )
    assert published.status_code == 200, published.text

    student_headers = auth(student)
    enroll = client.post(
        f"/api/courses/{course['id']}/enroll", headers=student_headers
    )
    assert enroll.status_code == 201, enroll.text
    enrollment_id = enroll.json()["enrollmentId"]

    fingerprint = "device-aoi"
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
    assert contents.status_code == 200, contents.text
    slide = contents.json()[0]
    return (
        course["id"],
        lesson["id"],
        session_id,
        slide["id"],
        slide["slideVersionId"],
        student_headers,
    )


def _presentation_and_layout(client, headers, session_id, membership_id):
    presentation = client.post(
        f"/api/learning-sessions/{session_id}/presentations",
        json={
            "lessonVersionSlideId": membership_id,
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
            "imageTransform": {
                "left": 0,
                "top": 0,
                "width": 1,
                "height": 1,
            },
            "rects": [
                {
                    "semanticCode": "slide",
                    "elementKey": "slide",
                    "xMin": 0,
                    "yMin": 0,
                    "xMax": 1,
                    "yMax": 1,
                },
                {
                    "semanticCode": "chatbot",
                    "elementKey": "chatbot",
                    "xMin": 0.6,
                    "yMin": 0,
                    "xMax": 1,
                    "yMax": 1,
                },
            ],
        },
        headers=headers,
    )
    assert layout.status_code == 201, layout.text
    return presentation_id, layout.json()["id"]


def _ingest(
    client,
    headers,
    session_id,
    presentation_id,
    layout_id,
    samples,
    *,
    batch_no=0,
    sequence_start=0,
):
    now = datetime.now(timezone.utc)
    payload = []
    for index, (x, y, status) in enumerate(samples):
        payload.append(
            {
                "sequence": sequence_start + index,
                "captureMonotonicNs": 1000 + index,
                "eventTime": (now + timedelta(milliseconds=index * 100)).isoformat(),
                "viewportX": x,
                "viewportY": y,
                "status": status,
                "qualityFlags": {},
            }
        )
    body = {
        "batchId": str(uuid.uuid4()),
        "batchNo": batch_no,
        "presentationId": presentation_id,
        "layoutSnapshotId": layout_id,
        "sequenceStart": sequence_start,
        "sequenceEnd": sequence_start + len(payload) - 1,
        "payloadHash": hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest(),
        "samples": payload,
    }
    response = client.post(
        f"/api/learning-sessions/{session_id}/gaze-batches",
        json=body,
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return body


def test_aoi_analysis_metrics_export_and_immutability(client, teacher, student):
    (
        course_id,
        lesson_id,
        session_id,
        membership_id,
        slide_version_id,
        student_headers,
    ) = _setup(client, teacher, student)
    teacher_headers = auth(teacher)

    aoi_set = client.post(
        "/api/aoi-sets",
        json={
            "scope": "slide",
            "slideVersionId": slide_version_id,
            "definitions": [
                {
                    "code": "title",
                    "name": "Tiêu đề",
                    "geometry": {"xMin": 0, "yMin": 0, "xMax": 1, "yMax": 1},
                }
            ],
        },
        headers=teacher_headers,
    )
    assert aoi_set.status_code == 201, aoi_set.text
    aoi_set_id = aoi_set.json()["id"]
    published = client.post(
        f"/api/aoi-sets/{aoi_set_id}/publish", headers=teacher_headers
    )
    assert published.status_code == 200, published.text
    assert published.json()["state"] == "published"

    immutable = client.patch(
        f"/api/aoi-sets/{aoi_set_id}",
        json={"definitions": []},
        headers=teacher_headers,
    )
    assert immutable.status_code == 409

    presentation_id, layout_id = _presentation_and_layout(
        client, student_headers, session_id, membership_id
    )
    _ingest(
        client,
        student_headers,
        session_id,
        presentation_id,
        layout_id,
        [(0.5, 0.5, "ok"), (0.51, 0.5, "ok"), (None, None, "no_face")],
    )

    now = datetime.now(timezone.utc)
    run = client.post(
        "/api/analysis-runs",
        json={
            "sessionId": session_id,
            "aoiSetId": aoi_set_id,
            "fromTime": (now - timedelta(minutes=5)).isoformat(),
            "toTime": (now + timedelta(minutes=5)).isoformat(),
            "algorithmVersion": "gaze-metrics-v1",
        },
        headers=teacher_headers,
    )
    assert run.status_code == 201, run.text
    result = run.json()
    assert result["run"]["status"] == "completed"
    assert result["hitCount"] >= 2
    assert result["metrics"][0]["sampleCount"] == 3
    assert result["metrics"][0]["onSlideCount"] == 2
    assert result["metrics"][0]["dwellMs"] > 0

    heatmap = client.get(
        f"/teacher/lessons/{lesson_id}/heatmap", headers=teacher_headers
    )
    assert heatmap.status_code == 200, heatmap.text
    assert heatmap.json()[0]["onSlide"] == pytest.approx(66.7, abs=0.1)
    assert heatmap.json()[0]["fixations"] >= 1

    students = client.get(
        f"/teacher/courses/{course_id}/students", headers=teacher_headers
    )
    assert students.status_code == 200, students.text
    row = students.json()[0]
    assert row["attention"] == pytest.approx(66.7, abs=0.1)
    assert row["lessons"][0]["mastery"] == pytest.approx(100.0, abs=0.1)

    export = client.get(
        f"/api/analysis-runs/{result['run']['id']}/export",
        headers=teacher_headers,
    )
    assert export.status_code == 200, export.text
    lines = [json.loads(line) for line in export.text.strip().splitlines()]
    assert lines[0]["type"] == "manifest"
    assert lines[0]["aoiSet"]["id"] == aoi_set_id
    assert any(line["type"] == "sample" for line in lines)
    assert lines[-1]["type"] == "end"

    # Run mới không xóa/không sửa kết quả run cũ.
    second = client.post(
        "/api/analysis-runs",
        json={
            "sessionId": session_id,
            "aoiSetId": aoi_set_id,
            "fromTime": (now - timedelta(minutes=5)).isoformat(),
            "toTime": (now + timedelta(minutes=5)).isoformat(),
            "algorithmVersion": "gaze-metrics-v1",
        },
        headers=teacher_headers,
    )
    assert second.status_code == 201, second.text
    first_again = client.get(
        f"/api/analysis-runs/{result['run']['id']}", headers=teacher_headers
    )
    assert first_again.status_code == 200
    assert first_again.json()["hitCount"] == result["hitCount"]

    # UI AOI set + layout rect hit.
    ui_set = client.post(
        "/api/aoi-sets",
        json={
            "scope": "ui",
            "uiSchemaVersion": "reader-v1",
            "definitions": [
                {
                    "code": "chatbot",
                    "name": "Khung chat",
                    "geometry": {"selector": '[data-aoi="chatbot"]'},
                }
            ],
        },
        headers=teacher_headers,
    )
    assert ui_set.status_code == 201, ui_set.text
    ui_set_id = ui_set.json()["id"]
    assert (
        client.post(
            f"/api/aoi-sets/{ui_set_id}/publish", headers=teacher_headers
        ).status_code
        == 200
    )
    _ingest(
        client,
        student_headers,
        session_id,
        presentation_id,
        layout_id,
        [(0.8, 0.5, "ok")],
        batch_no=1,
        sequence_start=3,
    )
    ui_run = client.post(
        "/api/analysis-runs",
        json={
            "sessionId": session_id,
            "aoiSetId": ui_set_id,
            "fromTime": (now - timedelta(minutes=5)).isoformat(),
            "toTime": (now + timedelta(minutes=5)).isoformat(),
            "algorithmVersion": "gaze-metrics-v1",
        },
        headers=teacher_headers,
    )
    assert ui_run.status_code == 201, ui_run.text
    assert ui_run.json()["hitCount"] >= 1

    rebuild = client.post(
        "/api/aoi/rebuild",
        json={"courseId": course_id},
        headers=teacher_headers,
    )
    assert rebuild.status_code == 200, rebuild.text
    assert rebuild.json()["runs"] >= 1
