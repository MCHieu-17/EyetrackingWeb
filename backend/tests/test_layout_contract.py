import uuid

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.gaze import ViewLayout
from tests.conftest import create_user, login, seed_course


async def _session_and_presentation(client, headers, ids):
    visit = await client.post(
        "/api/course-visits",
        headers=headers,
        json={"enrollmentId": ids["enrollment_id"], "visitKey": "layout-tab"},
    )
    assert visit.status_code == 201, visit.text
    session = await client.post(
        "/api/learning-sessions",
        headers=headers,
        json={
            "enrollmentId": ids["enrollment_id"],
            "lessonId": ids["lesson_id"],
            "courseVisitId": visit.json()["id"],
            "deviceFingerprint": "layout-test",
            "viewportWidthPx": 1280,
            "viewportHeightPx": 720,
            "calibrationWidthPx": 1280,
            "calibrationHeightPx": 720,
            "devicePixelRatio": 1.0,
            "trackingConsent": True,
        },
    )
    assert session.status_code == 201, session.text
    presentation = await client.post(
        f"/api/learning-sessions/{session.json()['id']}/presentations",
        headers=headers,
        json={"surface": "quiz", "sequenceNo": 0},
    )
    assert presentation.status_code == 201, presentation.text
    return session.json()["id"], presentation.json()["id"]


@pytest.mark.asyncio
async def test_layout_accepts_code_and_semantic_code(client):
    teacher_email = f"layout-t-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"layout-s-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    token = await login(client, student_email)
    headers = {"Authorization": f"Bearer {token}"}
    session_id, presentation_id = await _session_and_presentation(
        client, headers, ids
    )

    payload = {
        "sequenceNo": 0,
        "layoutGeneration": 0,
        "imageTransform": {"left": 0.1, "top": 0.1, "width": 0.8, "height": 0.8},
        "rects": [
            {"code": "header", "xMin": 0, "yMin": 0, "xMax": 1, "yMax": 0.1}
        ],
    }
    created = await client.post(
        f"/api/presentations/{presentation_id}/layouts",
        headers=headers,
        json=payload,
    )
    assert created.status_code == 201, created.text
    assert "coordinateSpace" not in created.json()
    assert "visibleRect" not in created.json()

    # Payload cũ với semanticCode vẫn phải được chấp nhận.
    legacy = await client.post(
        f"/api/presentations/{presentation_id}/layouts",
        headers=headers,
        json={
            **payload,
            "layoutGeneration": 1,
            "rects": [
                {
                    "semanticCode": "header",
                    "xMin": 0,
                    "yMin": 0,
                    "xMax": 1,
                    "yMax": 0.1,
                }
            ],
        },
    )
    assert legacy.status_code == 201, legacy.text

    # Sequence collision sau reload: cùng sequenceNo nhưng surface khác
    # phải được cấp sequence mới, không trả presentation cũ.
    second_presentation = await client.post(
        f"/api/learning-sessions/{session_id}/presentations",
        headers=headers,
        json={"surface": "lesson", "sequenceNo": 0},
    )
    assert second_presentation.status_code == 201, second_presentation.text
    assert second_presentation.json()["sequenceNo"] == 1
    assert second_presentation.json()["surface"] == "lesson"

    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(ViewLayout)
                .where(ViewLayout.content_view_id == presentation_id)
                .order_by(ViewLayout.layout_no)
            )
        ).scalars().all()
        assert len(rows) == 2
        assert rows[0].slide_rect["width"] == 0.8
        assert rows[0].elements[0]["code"] == "header"
        assert rows[1].elements[0]["code"] == "header"


@pytest.mark.asyncio
async def test_layout_rejects_original_v1_from_stale_client(client):
    teacher_email = f"layout-old-t-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"layout-old-s-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    token = await login(client, student_email)
    headers = {"Authorization": f"Bearer {token}"}
    _, presentation_id = await _session_and_presentation(client, headers, ids)

    response = await client.post(
        f"/api/presentations/{presentation_id}/layouts",
        headers=headers,
        json={
            "sequenceNo": 0,
            "layoutGeneration": 0,
            "coordinateSpace": "original-v1",
            "visibleRect": {
                "left": 0.1,
                "top": 0.1,
                "width": 0.8,
                "height": 0.8,
            },
            "imageTransform": {
                "left": 0.1,
                "top": 0.1,
                "width": 0.8,
                "height": 0.8,
            },
            "rects": [],
        },
    )
    assert response.status_code == 409
    assert "tải lại trang" in response.json()["detail"]
