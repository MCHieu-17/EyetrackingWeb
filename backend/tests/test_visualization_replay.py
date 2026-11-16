"""API replay ca học: overview + sample phân trang."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.session import SessionLocal
from app.models.aoi import Aoi
from app.models.gaze import (
    ContentView,
    CourseVisit,
    GazeSample,
    LearningSession,
    ViewLayout,
)
from app.services import metrics
from tests.conftest import create_user, login, seed_course, seed_slide


async def _seed_visit() -> dict[str, str]:
    teacher_email = f"replay-t-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"replay-s-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(
        email=student_email, full_name="Học viên Replay"
    )
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    slide = await seed_slide(
        course_id=ids["course_id"],
        lesson_id=ids["lesson_id"],
        teacher_id=teacher_id,
    )
    now = datetime.now(timezone.utc)
    header_code = f"header-{uuid.uuid4().hex[:8]}"

    async with SessionLocal() as db:
        db.add_all(
            [
                Aoi(
                    slide_id=slide["slide_id"],
                    code="text",
                    name="Thân bài",
                    label="AOI_THANHCHAT",
                    geometry={"xMin": 0.2, "yMin": 0.2, "xMax": 0.8, "yMax": 0.8},
                    kind="text",
                ),
                Aoi(
                    ui_schema="reader-v1",
                    code=header_code,
                    name="Thanh trên",
                    geometry={"selector": f"[data-aoi='{header_code}']"},
                    kind="ui",
                ),
            ]
        )
        visit = CourseVisit(
            enrollment_id=ids["enrollment_id"],
            started_at=now,
            last_seen_at=now,
            status="ended",
            ended_at=now + timedelta(minutes=5),
        )
        db.add(visit)
        await db.flush()
        session = LearningSession(
            enrollment_id=ids["enrollment_id"],
            lesson_id=ids["lesson_id"],
            course_visit_id=visit.id,
            viewport_width_px=1280,
            viewport_height_px=800,
            calibration_width_px=1280,
            calibration_height_px=800,
            expires_at=now + timedelta(hours=1),
        )
        db.add(session)
        await db.flush()
        view = ContentView(
            session_id=session.id,
            slide_id=slide["slide_id"],
            surface="lesson",
            sequence_no=0,
            started_at=now,
            ended_at=now + timedelta(minutes=2),
        )
        db.add(view)
        await db.flush()
        layout = ViewLayout(
            content_view_id=view.id,
            layout_no=0,
            slide_rect={"left": 0.2, "top": 0, "width": 0.6, "height": 1},
            elements=[
                {
                    "code": header_code,
                    "xMin": 0,
                    "yMin": 0,
                    "xMax": 1,
                    "yMax": 0.1,
                }
            ],
            captured_at=now,
        )
        db.add(layout)
        await db.flush()

        def sample(sequence: int, at_ms: int, x: float, y: float) -> GazeSample:
            return GazeSample(
                content_view_id=view.id,
                layout_id=layout.id,
                client_batch_id=uuid.uuid4(),
                sequence=sequence,
                event_time=now + timedelta(milliseconds=at_ms),
                viewport_x=x,
                viewport_y=y,
                status="ok",
            )

        db.add_all(
            [
                sample(0, 0, 0.5, 0.5),
                sample(1, 100, 0.5, 0.5),
                sample(2, 200, 0.1, 0.05),
            ]
        )
        await db.commit()
        await metrics.analyze_content_view(db, view.id)
        await db.commit()

    return {
        "teacher_email": teacher_email,
        "student_id": student_id,
        "visit_id": visit.id,
        "view_id": view.id,
        "layout_id": layout.id,
        "header_code": header_code,
    }


@pytest.mark.asyncio
async def test_replay_overview_contains_layouts_and_aoi_labels(client):
    data = await _seed_visit()
    token = await login(client, data["teacher_email"])
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        f"/teacher/visits/{data['visit_id']}/replay", headers=headers
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["student"]["name"] == "Học viên Replay"
    assert payload["visit"]["lessonSessionCount"] == 1
    assert len(payload["views"]) == 1
    view = payload["views"][0]
    assert view["slideTitle"] == "Slide 1"
    assert view["pdfUrl"].startswith("/media/assets/")
    assert view["viewport"]["width"] == 1280
    # Dwell wall time từ ended_at của view; 2 phút, không phải span sample.
    assert view["dwellMs"] == 120_000
    assert view["counted"] is True
    assert payload["visit"]["shortViewCount"] == 0
    assert payload["visit"]["minDwellMs"] == 1000

    slide_aois = {item["code"]: item for item in view["slideAois"]}
    assert slide_aois["text"]["analysisLabel"] == "SLIDE_AOI_THANHCHAT"
    assert slide_aois["text"]["name"] == "Thân bài"

    assert len(view["layouts"]) == 1
    layout = view["layouts"][0]
    assert "coordinateSpace" not in layout
    assert "visibleRect" not in layout
    assert layout["slideRect"]["width"] == 0.6
    ui_regions = {item["code"]: item for item in layout["uiRegions"]}
    assert data["header_code"] in ui_regions
    assert ui_regions[data["header_code"]]["name"] == "Thanh trên"
    assert ui_regions[data["header_code"]]["rects"][0]["xMax"] == 1.0

    stats = {item["label"]: item for item in view["aoiStats"]}
    assert stats["SLIDE_AOI_THANHCHAT"]["domain"] == "slide"
    assert stats["SLIDE_AOI_THANHCHAT"]["durationMs"] == 100
    assert stats["Thanh trên"]["domain"] == "ui"
    assert stats["Thanh trên"]["durationMs"] == 100


@pytest.mark.asyncio
async def test_replay_samples_keyset_pagination(client):
    data = await _seed_visit()
    token = await login(client, data["teacher_email"])
    headers = {"Authorization": f"Bearer {token}"}

    first = await client.get(
        f"/teacher/visits/{data['visit_id']}/samples",
        params={"contentViewId": data["view_id"], "limit": 2},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    page = first.json()
    assert page["contentViewId"] == data["view_id"]
    assert len(page["samples"]) == 2
    assert [item["offsetMs"] for item in page["samples"]] == [0, 100]
    assert page["nextCursor"] is not None

    cursor = page["nextCursor"]
    second = await client.get(
        f"/teacher/visits/{data['visit_id']}/samples",
        params={
            "contentViewId": data["view_id"],
            "limit": 2,
            "afterTime": cursor["afterTime"],
            "afterId": cursor["afterId"],
        },
        headers=headers,
    )
    assert second.status_code == 200, second.text
    page2 = second.json()
    assert len(page2["samples"]) == 1
    assert page2["samples"][0]["offsetMs"] == 200
    assert page2["nextCursor"] is None


@pytest.mark.asyncio
async def test_replay_is_scoped_to_visible_course(client):
    data = await _seed_visit()
    other_email = f"other-t-{uuid.uuid4().hex[:8]}@example.com"
    await create_user(email=other_email, role="teacher")
    other_token = await login(client, other_email)

    response = await client.get(
        f"/teacher/visits/{data['visit_id']}/replay",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert response.status_code in (403, 404)
