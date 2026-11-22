"""Presentation, layout, gaze batch: idempotency, validation, rate limit."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from tests.conftest import (
    create_course,
    create_lesson,
    create_slide,
    create_user,
    execute,
    fetch_one,
    login,
)

pytestmark = pytest.mark.fast

SESSION_BODY = {
    "deviceFingerprint": "gaze-device",
    "viewportWidthPx": 1280,
    "viewportHeightPx": 720,
    "calibrationWidthPx": 1280,
    "calibrationHeightPx": 720,
    "devicePixelRatio": 1.0,
    "trackingConsent": True,
}


async def _session_fixture(client, *, email="gaze@example.com"):
    teacher = await create_user(role="teacher", email=f"t-{email}")
    student = await create_user(email=email)
    ids = await create_course(
        teacher_id=teacher["id"],
        student_id=student["id"],
        status="published",
        require_calibration=False,
    )
    lesson_id = await create_lesson(module_id=ids["module_id"])
    slide_id = await create_slide(lesson_id=lesson_id)
    await login(client, student["email"])
    session = await client.post(
        "/api/learning-sessions",
        json={
            **SESSION_BODY,
            "enrollmentId": ids["enrollment_id"],
            "lessonId": lesson_id,
        },
    )
    assert session.status_code == 201, session.text
    return student, ids, lesson_id, slide_id, session.json()["id"]


async def _presentation(client, session_id, slide_id, *, client_id=None, **extra):
    payload = {
        "surface": "lesson",
        "slideId": slide_id,
        "clientPresentationId": client_id or str(uuid.uuid4()),
    }
    payload.update(extra)
    response = await client.post(
        f"/api/learning-sessions/{session_id}/presentations", json=payload
    )
    return response


async def test_presentation_idempotent_and_conflict(client):
    _, _, _, slide_id, session_id = await _session_fixture(client)
    client_id = str(uuid.uuid4())
    first = await _presentation(client, session_id, slide_id, client_id=client_id)
    assert first.status_code == 201, first.text
    assert first.json()["sequenceNo"] == 0

    same = await _presentation(client, session_id, slide_id, client_id=client_id)
    assert same.status_code == 201
    assert same.json()["id"] == first.json()["id"]
    assert (
        await fetch_one(
            "SELECT count(*) AS n FROM content_views WHERE session_id = :s",
            {"s": session_id},
        )
    )["n"] == 1

    # Cùng UUID nhưng khác slide -> conflict.
    other_slide = await create_slide(lesson_id=(await fetch_one(
        "SELECT lesson_id FROM slides WHERE id = :id", {"id": slide_id}
    ))["lesson_id"], position=1)
    conflict = await _presentation(
        client, session_id, other_slide, client_id=client_id
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "presentation_conflict"

    second = await _presentation(client, session_id, other_slide)
    assert second.status_code == 201
    assert second.json()["sequenceNo"] == 1


async def test_presentation_sequence_legacy_and_stale(client):
    _, _, _, slide_id, session_id = await _session_fixture(client)
    legacy = await client.post(
        f"/api/learning-sessions/{session_id}/presentations",
        json={"surface": "lesson", "slideId": slide_id, "sequenceNo": 0},
    )
    assert legacy.status_code == 201
    assert legacy.json()["sequenceNo"] == 0

    repeated = await client.post(
        f"/api/learning-sessions/{session_id}/presentations",
        json={"surface": "lesson", "slideId": slide_id, "sequenceNo": 0},
    )
    assert repeated.status_code == 201
    assert repeated.json()["id"] == legacy.json()["id"]

    other_slide = await create_slide(
        lesson_id=(await fetch_one(
            "SELECT lesson_id FROM slides WHERE id = :id", {"id": slide_id}
        ))["lesson_id"],
        position=2,
    )
    # sequenceNo cũ nhưng khác slide: phải cấp sequence mới, không trả row cũ.
    reused = await client.post(
        f"/api/learning-sessions/{session_id}/presentations",
        json={"surface": "lesson", "slideId": other_slide, "sequenceNo": 0},
    )
    assert reused.status_code == 201
    assert reused.json()["sequenceNo"] == 1

    now = datetime.now(UTC)
    stale = await _presentation(
        client,
        session_id,
        slide_id,
        enteredAt=(now - timedelta(seconds=2)).isoformat(),
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "stale_presentation"


async def test_presentation_entered_at_is_clamped(client):
    _, _, _, slide_id, session_id = await _session_fixture(
        client, email="gaze-clamp@example.com"
    )
    now = datetime.now(UTC)
    clamped = await _presentation(
        client,
        session_id,
        slide_id,
        enteredAt=(now - timedelta(hours=1)).isoformat(),
    )
    assert clamped.status_code == 201
    row = await fetch_one(
        "SELECT started_at FROM content_views WHERE id = :id",
        {"id": clamped.json()["id"]},
    )
    assert row["started_at"] >= now - timedelta(minutes=5, seconds=5)


async def test_presentation_rejects_slide_from_other_lesson(client):
    _, _, lesson_id, _, session_id = await _session_fixture(client)
    other_lesson = await create_lesson(
        module_id=(await fetch_one(
            "SELECT module_id FROM lessons WHERE id = :id", {"id": lesson_id}
        ))["module_id"],
        position=9,
    )
    other_slide = await create_slide(lesson_id=other_lesson)
    response = await _presentation(client, session_id, other_slide)
    assert response.status_code == 400
    assert response.json()["detail"] == "Slide không thuộc phiên học"


async def test_presentation_closed_session_grace(client):
    _, _, _, slide_id, session_id = await _session_fixture(client)
    await execute(
        "UPDATE learning_sessions SET status = 'completed', "
        "ended_at = now() - interval '3 minutes' WHERE id = :id",
        {"id": session_id},
    )
    response = await _presentation(client, session_id, slide_id)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "session_closed"


async def test_layout_create_deduplicate_and_coordinate_space(client):
    _, _, _, slide_id, session_id = await _session_fixture(client)
    presentation = await _presentation(client, session_id, slide_id)
    presentation_id = presentation.json()["id"]
    body = {
        "sequenceNo": 0,
        "layoutGeneration": 1,
        "imageTransform": {"left": 0.1, "top": 0.1, "width": 0.8, "height": 0.8},
        "rects": [
            {
                "semanticCode": "slide",
                "elementKey": "slide-1",
                "xMin": 0.1,
                "yMin": 0.1,
                "xMax": 0.9,
                "yMax": 0.9,
            }
        ],
    }
    first = await client.post(
        f"/api/presentations/{presentation_id}/layouts", json=body
    )
    assert first.status_code == 201, first.text
    layout_id = first.json()["id"]

    same = await client.post(
        f"/api/presentations/{presentation_id}/layouts", json=body
    )
    assert same.status_code == 201
    assert same.json()["id"] == layout_id
    assert (
        await fetch_one(
            "SELECT count(*) AS n FROM view_layouts WHERE content_view_id = :id",
            {"id": presentation_id},
        )
    )["n"] == 1
    stored = await fetch_one(
        "SELECT elements FROM view_layouts WHERE id = :id", {"id": layout_id}
    )
    assert stored["elements"][0]["code"] == "slide"

    old = {**body, "coordinateSpace": "original-v1"}
    rejected = await client.post(
        f"/api/presentations/{presentation_id}/layouts", json=old
    )
    assert rejected.status_code == 409

    foreign = await client.post(
        f"/api/presentations/{uuid.uuid4()}/layouts", json=body
    )
    assert foreign.status_code == 404


async def _batch(client, session_id, presentation_id, *, batch_id=None, samples=None):
    batch_id = batch_id or str(uuid.uuid4())
    samples = samples or [
        {
            "sequence": 0,
            "eventTime": datetime.now(UTC).isoformat(),
            "viewportX": 0.5,
            "viewportY": 0.5,
            "status": "ok",
            "qualityFlags": {},
        }
    ]
    return await client.post(
        f"/api/learning-sessions/{session_id}/gaze-batches",
        json={
            "batchId": batch_id,
            "presentationId": presentation_id,
            "sequenceStart": min(item["sequence"] for item in samples),
            "sequenceEnd": max(item["sequence"] for item in samples),
            "samples": samples,
        },
    )


async def test_gaze_batch_insert_and_duplicate(client):
    _, _, _, slide_id, session_id = await _session_fixture(client)
    presentation = await _presentation(client, session_id, slide_id)
    presentation_id = presentation.json()["id"]
    samples = [
        {
            "sequence": 0,
            "eventTime": datetime.now(UTC).isoformat(),
            "viewportX": 0.2,
            "viewportY": 0.3,
            "status": "ok",
            "qualityFlags": {"source": "test"},
        },
        {
            "sequence": 1,
            "eventTime": datetime.now(UTC).isoformat(),
            "viewportX": None,
            "viewportY": None,
            "status": "no_face",
            "qualityFlags": {},
        },
    ]
    batch_id = str(uuid.uuid4())
    first = await _batch(
        client, session_id, presentation_id, batch_id=batch_id, samples=samples
    )
    assert first.status_code == 200, first.text
    assert first.json() == {
        "ok": True,
        "batchId": batch_id,
        "received": 2,
        "stored": 2,
        "duplicate": 0,
        "rejected": 0,
    }
    stored = await fetch_one(
        "SELECT quality_flags FROM gaze_samples "
        "WHERE content_view_id = :id AND sequence = 0",
        {"id": presentation_id},
    )
    assert stored["quality_flags"]["source"] == "test"
    view = await fetch_one(
        "SELECT analysis_status FROM content_views WHERE id = :id",
        {"id": presentation_id},
    )
    assert view["analysis_status"] == "pending"

    # Duplicate batch không được đổi trạng thái đã phân tích xong.
    await execute(
        "UPDATE content_views SET analysis_status = 'ready' WHERE id = :id",
        {"id": presentation_id},
    )
    before = await fetch_one(
        "SELECT analysis_status, xmin::text AS xmin "
        "FROM content_views WHERE id = :id",
        {"id": presentation_id},
    )
    duplicate = await _batch(
        client, session_id, presentation_id, batch_id=batch_id, samples=samples
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["stored"] == 0
    assert duplicate.json()["duplicate"] == 2
    after = await fetch_one(
        "SELECT analysis_status, xmin::text AS xmin "
        "FROM content_views WHERE id = :id",
        {"id": presentation_id},
    )
    assert after == before

    # Batch mới có sample thật phải chuyển pending; batch kế tiếp lúc đã
    # pending không tạo thêm UPDATE.
    new_samples = [
        {
            "sequence": 2,
            "eventTime": datetime.now(UTC).isoformat(),
            "viewportX": 0.4,
            "viewportY": 0.4,
            "status": "ok",
            "qualityFlags": {},
        },
        {
            "sequence": 3,
            "eventTime": datetime.now(UTC).isoformat(),
            "viewportX": 0.5,
            "viewportY": 0.5,
            "status": "ok",
            "qualityFlags": {},
        },
    ]
    third = await _batch(client, session_id, presentation_id, samples=new_samples)
    assert third.status_code == 200, third.text
    assert third.json()["stored"] == 2
    before = await fetch_one(
        "SELECT analysis_status, xmin::text AS xmin "
        "FROM content_views WHERE id = :id",
        {"id": presentation_id},
    )
    assert before["analysis_status"] == "pending"

    more_samples = [
        {**sample, "sequence": sample["sequence"] + 2} for sample in new_samples
    ]
    fourth = await _batch(
        client, session_id, presentation_id, samples=more_samples
    )
    assert fourth.status_code == 200, fourth.text
    assert fourth.json()["stored"] == 2
    after = await fetch_one(
        "SELECT analysis_status, xmin::text AS xmin "
        "FROM content_views WHERE id = :id",
        {"id": presentation_id},
    )
    assert after == before


@pytest.mark.parametrize(
    "samples",
    [
        [
            {
                "sequence": 0,
                "eventTime": "2026-01-01T00:00:00Z",
                "viewportX": None,
                "viewportY": None,
                "status": "ok",
            }
        ],
        [
            {
                "sequence": 0,
                "eventTime": "2026-01-01T00:00:00Z",
                "viewportX": 0.1,
                "viewportY": 0.1,
                "status": "no_face",
            }
        ],
        [
            {
                "sequence": 1,
                "eventTime": "2026-01-01T00:00:01Z",
                "viewportX": 0.1,
                "viewportY": 0.1,
                "status": "ok",
            },
            {
                "sequence": 0,
                "eventTime": "2026-01-01T00:00:02Z",
                "viewportX": 0.1,
                "viewportY": 0.1,
                "status": "ok",
            },
        ],
    ],
)
async def test_gaze_batch_validation(client, samples):
    _, _, _, slide_id, session_id = await _session_fixture(client)
    presentation = await _presentation(client, session_id, slide_id)
    response = await client.post(
        f"/api/learning-sessions/{session_id}/gaze-batches",
        json={
            "batchId": "bad",
            "presentationId": presentation.json()["id"],
            "sequenceStart": 0,
            "sequenceEnd": max(item["sequence"] for item in samples),
            "samples": samples,
        },
    )
    assert response.status_code == 422


async def test_gaze_batch_rate_limit(client):
    _, _, _, slide_id, session_id = await _session_fixture(client)
    presentation = await _presentation(client, session_id, slide_id)
    presentation_id = presentation.json()["id"]
    sample = [
        {
            "sequence": 0,
            "eventTime": datetime.now(UTC).isoformat(),
            "viewportX": 0.1,
            "viewportY": 0.1,
            "status": "ok",
        }
    ]
    for _ in range(120):
        response = await _batch(
            client,
            session_id,
            presentation_id,
            batch_id=str(uuid.uuid4()),
            samples=sample,
        )
        assert response.status_code == 200, response.text
    limited = await _batch(
        client,
        session_id,
        presentation_id,
        batch_id=str(uuid.uuid4()),
        samples=sample,
    )
    assert limited.status_code == 429
    assert limited.headers["Retry-After"] == "60"
