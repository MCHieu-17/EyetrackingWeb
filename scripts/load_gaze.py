#!/usr/bin/env python3
"""Synthetic gaze ingestion load test.

Mặc định 2.000 samples/s trong 30 phút. Mỗi giây gửi một batch 2.000 samples
(batchNo tăng dần), đúng rate limit 120 batch/phút.

    python3 scripts/load_gaze.py --seconds 1800 --rate 2000
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import statistics
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pymupdf

BASE = "http://localhost:8001"
PASSWORD = "Password123!"


def _pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Load test slide")
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


def _setup(client: httpx.Client) -> tuple[str, str, str, str]:
    teacher_token = _login(client, "teacher@school.edu.vn")
    teacher = _auth(teacher_token)
    course = client.post(
        "/teacher/courses",
        headers=teacher,
        json={"title": f"Load test {uuid.uuid4().hex[:6]}"},
    )
    course.raise_for_status()
    course_id = course.json()["id"]
    module = client.post(
        f"/teacher/courses/{course_id}/modules",
        headers=teacher,
        json={"title": "Load module"},
    )
    module.raise_for_status()
    lesson = client.post(
        f"/teacher/modules/{module.json()['id']}/lessons",
        headers=teacher,
        json={"title": "Load lesson"},
    )
    lesson.raise_for_status()
    lesson_id = lesson.json()["id"]
    upload = client.post(
        f"/teacher/lessons/{lesson_id}/slides/upload",
        headers=teacher,
        files={"pdf": ("load.pdf", _pdf(), "application/pdf")},
    )
    upload.raise_for_status()
    published = client.post(
        f"/teacher/courses/{course_id}/publish", headers=teacher, json={}
    )
    published.raise_for_status()

    email = f"load-{uuid.uuid4().hex[:8]}@example.com"
    registered = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "fullName": "Load Student",
            "birthYear": 2004,
        },
    )
    registered.raise_for_status()
    student = _auth(registered.json()["accessToken"])
    enroll = client.post(f"/api/courses/{course_id}/enroll", headers=student)
    enroll.raise_for_status()
    enrollment_id = enroll.json()["enrollmentId"]

    fingerprint = f"load-{uuid.uuid4().hex[:8]}"
    calibration = client.post(
        "/api/calibrations",
        headers=student,
        json={
            "deviceFingerprint": fingerprint,
            "numPoints": 16,
            "modelUbjBase64": base64.b64encode(b"load-model").decode(),
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
    return (
        session_id,
        presentation_id,
        layout.json()["id"],
        registered.json()["accessToken"],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=1800)
    parser.add_argument("--rate", type=int, default=2000)
    parser.add_argument("--batch-size", type=int, default=2000)
    args = parser.parse_args()

    with httpx.Client(base_url=BASE, timeout=120) as client:
        session_id, presentation_id, layout_id, student_token = _setup(client)
        student = _auth(student_token)
        batch_size = min(args.batch_size, 2000)
        batches_per_second = max(1, args.rate // batch_size)
        total_batches = args.seconds * batches_per_second
        sequence = 0
        batch_no = 0
        latencies: list[float] = []
        stored = 0
        started = time.monotonic()
        next_tick = started

        print(
            json.dumps(
                {
                    "sessionId": session_id,
                    "presentationId": presentation_id,
                    "layoutId": layout_id,
                    "rate": args.rate,
                    "seconds": args.seconds,
                    "totalBatches": total_batches,
                }
            ),
            flush=True,
        )

        for index in range(total_batches):
            now = datetime.now(timezone.utc)
            samples = []
            for offset in range(batch_size):
                samples.append(
                    {
                        "sequence": sequence + offset,
                        "captureMonotonicNs": (sequence + offset) * 500_000,
                        "eventTime": (
                            now + timedelta(microseconds=500 * offset)
                        ).isoformat(),
                        "viewportX": 0.5,
                        "viewportY": 0.5,
                        "status": "ok",
                        "qualityFlags": {},
                    }
                )
            body = {
                "batchId": str(uuid.uuid4()),
                "batchNo": batch_no,
                "presentationId": presentation_id,
                "layoutSnapshotId": layout_id,
                "sequenceStart": sequence,
                "sequenceEnd": sequence + batch_size - 1,
                "payloadHash": hashlib.sha256(
                    json.dumps(samples, sort_keys=True).encode()
                ).hexdigest(),
                "samples": samples,
            }
            request_started = time.monotonic()
            response = client.post(
                f"/api/learning-sessions/{session_id}/gaze-batches",
                headers=student,
                json=body,
            )
            response.raise_for_status()
            latencies.append((time.monotonic() - request_started) * 1000)
            stored += int(response.json().get("stored", 0))
            sequence += batch_size
            batch_no += 1

            if (index + 1) % 60 == 0:
                elapsed = time.monotonic() - started
                print(
                    json.dumps(
                        {
                            "batches": index + 1,
                            "samples": stored,
                            "elapsedSec": round(elapsed, 1),
                            "effectiveRate": round(stored / elapsed, 1),
                            "p50Ms": round(statistics.median(latencies[-60:]), 1),
                            "p95Ms": round(
                                sorted(latencies[-60:])[
                                    max(0, int(len(latencies[-60:]) * 0.95) - 1)
                                ],
                                1,
                            ),
                        }
                    ),
                    flush=True,
                )

            next_tick += 1 / batches_per_second
            sleep_for = next_tick - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)

        elapsed = time.monotonic() - started
        print(
            json.dumps(
                {
                    "ok": True,
                    "batches": batch_no,
                    "samples": stored,
                    "elapsedSec": round(elapsed, 1),
                    "effectiveRate": round(stored / elapsed, 1),
                    "p50Ms": round(statistics.median(latencies), 1),
                    "p95Ms": round(
                        sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 1
                    ),
                    "maxMs": round(max(latencies), 1),
                }
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
