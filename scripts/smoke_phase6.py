#!/usr/bin/env python3
"""Smoke lifecycle trên stack development sau Phase 6.

Chạy:
    python3 scripts/smoke_phase6.py
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pymupdf

BASE = "http://localhost:8001"
PASSWORD = "Password123!"
NEW_PASSWORD = "Password123!New"


def _pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Phase 6 smoke slide")
    data = doc.tobytes()
    doc.close()
    return data


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(client: httpx.Client, email: str) -> str:
    response = client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    response.raise_for_status()
    return response.json()["accessToken"]


def _ensure_password_changed(client: httpx.Client, token: str) -> str:
    response = client.get("/api/me/profile", headers=_auth(token))
    if response.status_code != 403 or response.json().get("detail") != "PASSWORD_CHANGE_REQUIRED":
        return token
    changed = client.post(
        "/api/auth/change-password",
        headers=_auth(token),
        json={"currentPassword": PASSWORD, "newPassword": NEW_PASSWORD},
    )
    changed.raise_for_status()
    response = client.post(
        "/api/auth/login",
        json={"email": "teacher@school.edu.vn", "password": NEW_PASSWORD},
    )
    response.raise_for_status()
    return response.json()["accessToken"]


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=120) as client:
        teacher_token = _ensure_password_changed(
            client, _login(client, "teacher@school.edu.vn")
        )
        teacher = _auth(teacher_token)

        course = client.post(
            "/teacher/courses",
            headers=teacher,
            json={"title": f"Smoke Phase 6 {uuid.uuid4().hex[:6]}"},
        )
        course.raise_for_status()
        course_id = course.json()["id"]

        module = client.post(
            f"/teacher/courses/{course_id}/modules",
            headers=teacher,
            json={"title": "Chương smoke"},
        )
        module.raise_for_status()
        module_id = module.json()["id"]

        lesson = client.post(
            f"/teacher/modules/{module_id}/lessons",
            headers=teacher,
            json={"title": "Bài smoke"},
        )
        lesson.raise_for_status()
        lesson_id = lesson.json()["id"]

        upload = client.post(
            f"/teacher/lessons/{lesson_id}/slides/upload",
            headers=teacher,
            files={"pdf": ("smoke.pdf", _pdf(), "application/pdf")},
        )
        upload.raise_for_status()

        published = client.post(
            f"/teacher/courses/{course_id}/publish", headers=teacher, json={}
        )
        published.raise_for_status()

        email = f"smoke-{uuid.uuid4().hex[:8]}@example.com"
        registered = client.post(
            "/api/auth/register",
            json={
                "email": email,
                "password": PASSWORD,
                "fullName": "Smoke Student",
                "birthYear": 2004,
            },
        )
        registered.raise_for_status()
        student_token = registered.json()["accessToken"]
        student = _auth(student_token)

        enroll = client.post(f"/api/courses/{course_id}/enroll", headers=student)
        enroll.raise_for_status()
        enrollment_id = enroll.json()["enrollmentId"]

        fingerprint = f"smoke-{uuid.uuid4().hex[:8]}"
        calibration = client.post(
            "/api/calibrations",
            headers=student,
            json={
                "deviceFingerprint": fingerprint,
                "numPoints": 16,
                "modelUbjBase64": base64.b64encode(b"smoke-model").decode(),
                "viewportWidthPx": 1280,
                "viewportHeightPx": 720,
                "devicePixelRatio": 1,
            },
        )
        calibration.raise_for_status()

        session = client.post(
            "/api/learning-sessions",
            headers=student,
            json={
                "enrollmentId": enrollment_id,
                "lessonId": lesson_id,
                "deviceFingerprint": fingerprint,
                "viewportWidthPx": 1280,
                "viewportHeightPx": 720,
                "calibrationWidthPx": 1280,
                "calibrationHeightPx": 720,
                "devicePixelRatio": 1,
                "trackingConsent": True,
            },
        )
        session.raise_for_status()
        session_id = session.json()["id"]

        contents = client.get(
            f"/api/learning-sessions/{session_id}/contents", headers=student
        )
        contents.raise_for_status()
        slide = contents.json()[0]

        presentation = client.post(
            f"/api/learning-sessions/{session_id}/presentations",
            headers=student,
            json={
                "lessonVersionSlideId": slide["id"],
                "surface": "lesson",
                "sequenceNo": 0,
            },
        )
        presentation.raise_for_status()
        presentation_id = presentation.json()["id"]

        layout = client.post(
            f"/api/presentations/{presentation_id}/layouts",
            headers=student,
            json={
                "sequenceNo": 0,
                "layoutGeneration": 0,
                "imageTransform": {"left": 0, "top": 0, "width": 1, "height": 1},
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
        )
        layout.raise_for_status()
        layout_id = layout.json()["id"]

        now = datetime.now(timezone.utc)
        samples = [
            {
                "sequence": index,
                "captureMonotonicNs": 1000 + index,
                "eventTime": (now + timedelta(milliseconds=index * 100)).isoformat(),
                "viewportX": 0.5,
                "viewportY": 0.5,
                "status": "ok",
                "qualityFlags": {},
            }
            for index in range(3)
        ]
        batch = client.post(
            f"/api/learning-sessions/{session_id}/gaze-batches",
            headers=student,
            json={
                "batchId": str(uuid.uuid4()),
                "batchNo": 0,
                "presentationId": presentation_id,
                "layoutSnapshotId": layout_id,
                "sequenceStart": 0,
                "sequenceEnd": 2,
                "payloadHash": hashlib.sha256(
                    json.dumps(samples, sort_keys=True).encode()
                ).hexdigest(),
                "samples": samples,
            },
        )
        batch.raise_for_status()

        aoi = client.post(
            "/api/aoi-sets",
            headers=teacher,
            json={
                "scope": "slide",
                "slideVersionId": slide["slideVersionId"],
                "definitions": [
                    {
                        "code": "slide",
                        "name": "Toàn slide",
                        "geometry": {"xMin": 0, "yMin": 0, "xMax": 1, "yMax": 1},
                    }
                ],
            },
        )
        aoi.raise_for_status()
        aoi_id = aoi.json()["id"]
        client.post(f"/api/aoi-sets/{aoi_id}/publish", headers=teacher).raise_for_status()

        run = client.post(
            "/api/analysis-runs",
            headers=teacher,
            json={
                "sessionId": session_id,
                "aoiSetId": aoi_id,
                "fromTime": (now - timedelta(minutes=5)).isoformat(),
                "toTime": (now + timedelta(minutes=5)).isoformat(),
            },
        )
        run.raise_for_status()
        run_body = run.json()

        heatmap = client.get(
            f"/teacher/lessons/{lesson_id}/heatmap", headers=teacher
        )
        heatmap.raise_for_status()

        export = client.get(
            f"/api/analysis-runs/{run_body['run']['id']}/export", headers=teacher
        )
        export.raise_for_status()

        access = client.get(
            f"/api/courses/{course_id}/chat/access", headers=student
        )
        access.raise_for_status()

        print(
            json.dumps(
                {
                    "ok": True,
                    "courseId": course_id,
                    "lessonId": lesson_id,
                    "sessionId": session_id,
                    "analysisRunId": run_body["run"]["id"],
                    "hitCount": run_body["hitCount"],
                    "metrics": len(run_body["metrics"]),
                    "heatmapSlides": len(heatmap.json()),
                    "exportLines": len(export.text.strip().splitlines()),
                    "chatAllowed": access.json()["allowed"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
