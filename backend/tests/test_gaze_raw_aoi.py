"""Tests cho gaze raw + AOI DOM-anchored (migration 026)."""

import asyncio

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from tests.conftest import auth
from tests.test_flow import _setup_course

VIEWPORT = {
    "viewportWidthPx": 1280,
    "viewportHeightPx": 720,
    "calibrationWidthPx": 1280,
    "calibrationHeightPx": 720,
    "devicePixelRatio": 1,
}


def _create_session(client, student, enrollment_id, lesson_id, **overrides):
    payload = {
        "enrollmentId": enrollment_id,
        "lessonId": lesson_id,
        "deviceFingerprint": "fp-raw",
        "trackingConsent": True,
        **VIEWPORT,
        **overrides,
    }
    return client.post("/api/learning-sessions", headers=auth(student), json=payload)


def _raw_rows(session_id: str):
    async def run():
        async with SessionLocal() as db:
            return (
                await db.execute(
                    text(
                        "SELECT gaze_x, gaze_y, status, viewport_width_px, "
                        "calibration_width_px, layout_snapshot_id "
                        "FROM gaze_raw_samples WHERE learning_session_id = :sid "
                        "ORDER BY event_time"
                    ),
                    {"sid": session_id},
                )
            ).all()

    return asyncio.run(run())


def _hit_rows(session_id: str):
    async def run():
        async with SessionLocal() as db:
            return (
                await db.execute(
                    text(
                        "SELECT d.code FROM gaze_aoi_hits h "
                        "JOIN aoi_definitions d ON d.id = h.aoi_id "
                        "WHERE h.learning_session_id = :sid ORDER BY d.code"
                    ),
                    {"sid": session_id},
                )
            ).all()

    return asyncio.run(run())


def test_raw_samples_store_offscreen_and_no_face(client):
    teacher, student, course_id, lesson_id, slide_ids = _setup_course(client)
    enrollment_id = client.post(
        f"/api/courses/{course_id}/enroll", headers=auth(student)
    ).json()["enrollmentId"]

    r = _create_session(client, student, enrollment_id, lesson_id)
    assert r.status_code == 201, r.text
    session = r.json()
    assert session["viewportWidthPx"] == 1280
    assert session["calibrationWidthPx"] == 1280

    samples = [
        {
            "lessonContentId": slide_ids[0],
            "x": 0.3,
            "y": 0.4,
            "slideX": 0.3,
            "slideY": 0.4,
            "ts": 1755000000000,
        },
        {
            "lessonContentId": slide_ids[0],
            "x": 1.5,
            "y": 0.5,
            "slideX": 1.5,
            "slideY": 0.5,
            "ts": 1755000000300,
        },
        {
            "lessonContentId": slide_ids[0],
            "x": -1,
            "y": -1,
            "faceDetected": False,
            "ts": 1755000000600,
        },
    ]
    r = client.post(
        f"/api/lessons/{lesson_id}/gaze-samples",
        headers=auth(student),
        json={
            "learningSessionId": session["id"],
            "samples": samples,
            "viewportWidthPx": 1280,
            "viewportHeightPx": 720,
        },
    )
    assert r.status_code == 200, r.text

    rows = _raw_rows(session["id"])
    assert len(rows) == 3
    assert rows[0][0] == pytest.approx(0.3) and rows[0][2] == "ok"
    assert rows[1][0] == pytest.approx(1.5) and rows[1][2] == "ok"
    assert rows[2][0] is None and rows[2][2] == "no_face"
    assert all(row[3] == row[4] == 1280 for row in rows)


def test_raw_downsample_hz(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "gaze_raw_hz", 1.0)

    teacher, student, course_id, lesson_id, slide_ids = _setup_course(client)
    enrollment_id = client.post(
        f"/api/courses/{course_id}/enroll", headers=auth(student)
    ).json()["enrollmentId"]

    r = _create_session(client, student, enrollment_id, lesson_id)
    assert r.status_code == 201, r.text
    session = r.json()

    samples = [
        {
            "lessonContentId": slide_ids[0],
            "x": 0.3,
            "y": 0.4,
            "slideX": 0.3,
            "slideY": 0.4,
            "ts": 1755000000000 + i * 300,
        }
        for i in range(4)
    ]
    r = client.post(
        f"/api/lessons/{lesson_id}/gaze-samples",
        headers=auth(student),
        json={
            "learningSessionId": session["id"],
            "samples": samples,
            "viewportWidthPx": 1280,
            "viewportHeightPx": 720,
        },
    )
    assert r.status_code == 200, r.text
    # 1Hz: chỉ giữ sample đầu, 3 sample sau cách nhau 300ms < 1000ms.
    assert len(_raw_rows(session["id"])) == 1


def test_viewport_mismatch_rejected(client):
    teacher, student, course_id, lesson_id, slide_ids = _setup_course(client)
    enrollment_id = client.post(
        f"/api/courses/{course_id}/enroll", headers=auth(student)
    ).json()["enrollmentId"]

    r = _create_session(
        client,
        student,
        enrollment_id,
        lesson_id,
        viewportWidthPx=1920,
        viewportHeightPx=1080,
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "viewport_mismatch"

    r = _create_session(client, student, enrollment_id, lesson_id)
    assert r.status_code == 201, r.text
    session = r.json()

    r = client.post(
        f"/api/lessons/{lesson_id}/gaze-samples",
        headers=auth(student),
        json={
            "learningSessionId": session["id"],
            "samples": [
                {
                    "lessonContentId": slide_ids[0],
                    "x": 0.3,
                    "y": 0.4,
                    "slideX": 0.3,
                    "slideY": 0.4,
                    "ts": 1755000000000,
                }
            ],
            "viewportWidthPx": 1920,
            "viewportHeightPx": 1080,
        },
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "viewport_mismatch"
    assert _raw_rows(session["id"]) == []


def test_aoi_snapshot_and_rebuild_can_add_aoi_later(client):
    teacher, student, course_id, lesson_id, slide_ids = _setup_course(client)
    enrollment_id = client.post(
        f"/api/courses/{course_id}/enroll", headers=auth(student)
    ).json()["enrollmentId"]

    r = _create_session(client, student, enrollment_id, lesson_id)
    assert r.status_code == 201, r.text
    session = r.json()

    # Catalog ban đầu: slide, chatbot, chat-user-message.
    defs = {}
    for code, name, parent in [
        ("slide", "Bài giảng", None),
        ("chatbot", "Khung chatbot", None),
        ("chat-user-message", "Tin nhắn người dùng", "chatbot"),
    ]:
        r = client.post(
            "/api/aoi-definitions",
            headers=auth(teacher),
            json={
                "code": code,
                "name": name,
                "parentId": defs.get(parent),
                "selector": f'[data-aoi="{code}"]',
            },
        )
        assert r.status_code == 201, r.text
        defs[code] = r.json()["id"]

    # Snapshot gửi TẤT CẢ rect, kể cả chat-ai-message chưa có definition.
    r = client.post(
        f"/api/learning-sessions/{session['id']}/aoi-layout",
        headers=auth(student),
        json={
            "viewportWidthPx": 1280,
            "viewportHeightPx": 720,
            "layoutKey": "reader-desktop",
            "rects": [
                {"code": "slide", "xMin": 0.1, "yMin": 0.1, "xMax": 0.6, "yMax": 0.9},
                {"code": "chatbot", "xMin": 0.7, "yMin": 0.1, "xMax": 0.99, "yMax": 0.9},
                {
                    "code": "chat-user-message",
                    "xMin": 0.75,
                    "yMin": 0.2,
                    "xMax": 0.95,
                    "yMax": 0.3,
                },
                {
                    "code": "chat-ai-message",
                    "xMin": 0.75,
                    "yMin": 0.4,
                    "xMax": 0.95,
                    "yMax": 0.5,
                },
            ],
        },
    )
    assert r.status_code == 201, r.text
    snapshot_id = r.json()["id"]

    samples = [
        {
            "lessonContentId": slide_ids[0],
            "x": 0.3,
            "y": 0.5,
            "slideX": 0.3,
            "slideY": 0.5,
            "ts": 1755000000000,
        },
        {
            "lessonContentId": slide_ids[0],
            "x": 0.8,
            "y": 0.25,
            "slideX": 0.8,
            "slideY": 0.25,
            "ts": 1755000000300,
        },
        {
            "lessonContentId": slide_ids[0],
            "x": 0.8,
            "y": 0.45,
            "slideX": 0.8,
            "slideY": 0.45,
            "ts": 1755000000600,
        },
    ]
    r = client.post(
        f"/api/lessons/{lesson_id}/gaze-samples",
        headers=auth(student),
        json={
            "learningSessionId": session["id"],
            "samples": samples,
            "viewportWidthPx": 1280,
            "viewportHeightPx": 720,
            "layoutSnapshotId": snapshot_id,
        },
    )
    assert r.status_code == 200, r.text

    r = client.post(
        "/api/aoi/rebuild",
        headers=auth(teacher),
        json={"sessionId": session["id"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["inserted"] == 4  # slide + chatbot + chat-user-message + chatbot

    hits = sorted(row[0] for row in _hit_rows(session["id"]))
    assert hits == sorted(["chat-user-message", "chatbot", "chatbot", "slide"])

    # Thêm AOI chat-ai-message SAU khi đã có snapshot + raw.
    r = client.post(
        "/api/aoi-definitions",
        headers=auth(teacher),
        json={
            "code": "chat-ai-message",
            "name": "Tin nhắn AI",
            "parentId": defs["chatbot"],
            "selector": '[data-aoi="chat-ai-message"]',
        },
    )
    assert r.status_code == 201, r.text

    r = client.post(
        "/api/aoi/rebuild",
        headers=auth(teacher),
        json={"sessionId": session["id"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["inserted"] == 5

    hits = sorted(row[0] for row in _hit_rows(session["id"]))
    assert hits == sorted(
        [
            "chat-ai-message",
            "chat-user-message",
            "chatbot",
            "chatbot",
            "slide",
        ]
    )


def test_aoi_definition_crud(client):
    teacher, _, _, _, _ = _setup_course(client)

    r = client.post(
        "/api/aoi-definitions",
        headers=auth(teacher),
        json={"code": "slide", "name": "Bài giảng"},
    )
    assert r.status_code == 201, r.text
    aoi_id = r.json()["id"]

    r = client.post(
        "/api/aoi-definitions",
        headers=auth(teacher),
        json={"code": "slide", "name": "Trùng"},
    )
    assert r.status_code == 409, r.text

    r = client.get("/api/aoi-definitions", headers=auth(teacher))
    assert r.status_code == 200, r.text
    assert [item["code"] for item in r.json()] == ["slide"]

    r = client.patch(
        f"/api/aoi-definitions/{aoi_id}",
        headers=auth(teacher),
        json={"name": "Vùng bài giảng"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Vùng bài giảng"

    r = client.delete(f"/api/aoi-definitions/{aoi_id}", headers=auth(teacher))
    assert r.status_code == 200, r.text

    r = client.get("/api/aoi-definitions", headers=auth(teacher))
    assert r.json() == []
    r = client.get(
        "/api/aoi-definitions",
        headers=auth(teacher),
        params={"include_inactive": True},
    )
    assert len(r.json()) == 1
    assert r.json()[0]["isActive"] is False
