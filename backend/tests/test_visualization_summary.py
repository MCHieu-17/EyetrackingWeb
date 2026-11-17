"""Dashboard tổng hợp AOI: phạm vi, bộ lọc và heatmap."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.db.session import SessionLocal
from app.models.aoi import Aoi
from app.models.course import Enrollment
from app.models.gaze import (
    ContentView,
    CourseVisit,
    GazeSample,
    LearningSession,
    ViewLayout,
)
from app.services import metrics
from tests.conftest import create_user, login, seed_course, seed_slide


async def _seed_summary_data() -> dict:
    teacher_email = f"sum-t-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student1_id = await create_user(
        email=f"sum-s1-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Sinh viên Một",
    )
    student2_id = await create_user(
        email=f"sum-s2-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Sinh viên Hai",
    )
    ids = await seed_course(teacher_id=teacher_id, student_id=student1_id)
    slide = await seed_slide(
        course_id=ids["course_id"],
        lesson_id=ids["lesson_id"],
        teacher_id=teacher_id,
    )
    header_code = f"header-{uuid.uuid4().hex[:8]}"

    async with SessionLocal() as db:
        enrollment2 = Enrollment(
            course_id=ids["course_id"], student_id=student2_id, status="active"
        )
        db.add(enrollment2)
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
        await db.flush()
        await db.commit()

    now = datetime.now(timezone.utc)

    async def create_visit(enrollment_id: str, offset_minutes: int) -> dict:
        async with SessionLocal() as db:
            visit = CourseVisit(
                enrollment_id=enrollment_id,
                started_at=now + timedelta(minutes=offset_minutes),
                last_seen_at=now + timedelta(minutes=offset_minutes),
                status="ended",
                ended_at=now + timedelta(minutes=offset_minutes + 5),
            )
            db.add(visit)
            await db.flush()
            session = LearningSession(
                enrollment_id=enrollment_id,
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
                started_at=visit.started_at,
                ended_at=visit.started_at + timedelta(seconds=30),
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
                captured_at=visit.started_at,
            )
            db.add(layout)
            await db.flush()

            def sample(sequence: int, at_ms: int, x: float, y: float) -> GazeSample:
                return GazeSample(
                    content_view_id=view.id,
                    layout_id=layout.id,
                    client_batch_id=uuid.uuid4(),
                    sequence=sequence,
                    event_time=visit.started_at + timedelta(milliseconds=at_ms),
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
                "visit_id": visit.id,
                "view_id": view.id,
            }

    async with SessionLocal() as db:
        enrollment1 = (
            await db.execute(
                Enrollment.__table__.select().where(
                    Enrollment.id == ids["enrollment_id"]
                )
            )
        ).mappings().one()
        enrollment2_id = (
            await db.execute(
                Enrollment.__table__.select().where(
                    Enrollment.student_id == student2_id,
                    Enrollment.course_id == ids["course_id"],
                )
            )
        ).mappings().one()["id"]

    visits1 = [
        await create_visit(enrollment1["id"], 0),
        await create_visit(enrollment1["id"], 30),
    ]
    visits2 = [
        await create_visit(enrollment2_id, 60),
        await create_visit(enrollment2_id, 90),
    ]

    return {
        "teacher_email": teacher_email,
        "course_id": ids["course_id"],
        "lesson_id": ids["lesson_id"],
        "slide_id": slide["slide_id"],
        "student1_id": student1_id,
        "student2_id": student2_id,
        "enrollment2_id": enrollment2_id,
        "visits1": visits1,
        "visits2": visits2,
    }


async def _post_summary(client, headers, course_id, body):
    return await client.post(
        f"/teacher/courses/{course_id}/analytics/aoi-summary",
        headers=headers,
        json=body,
    )


@pytest.mark.asyncio
async def test_summary_scopes_and_breakdowns(client):
    data = await _seed_summary_data()
    token = await login(client, data["teacher_email"])
    headers = {"Authorization": f"Bearer {token}"}

    # Một ca của một sinh viên.
    response = await _post_summary(
        client,
        headers,
        data["course_id"],
        {"visitIds": [data["visits1"][0]["visit_id"]]},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["totals"]["visitCount"] == 1
    assert payload["totals"]["studentCount"] == 1
    assert payload["totals"]["trackedDurationMs"] == 200
    assert payload["totals"]["labeledDurationMs"] == 200
    assert payload["totals"]["unmappedDurationMs"] == 0
    assert payload["meta"]["includeShort"] is True
    assert payload["meta"]["minDwellMs"] == 1000
    assert payload["meta"]["maxGapMs"] == 250
    assert payload["meta"]["shortViewCount"] == 0
    by_label = {item["label"]: item for item in payload["byAoi"]}
    assert by_label["SLIDE_AOI_THANHCHAT"]["name"] == "Thân bài"
    assert by_label["SLIDE_AOI_THANHCHAT"]["durationMs"] == 100
    assert by_label["Thanh trên"]["durationMs"] == 100
    assert any(item["name"] == "Thanh trên" for item in payload["byAoi"])

    # Nhiều ca của một sinh viên.
    response = await _post_summary(
        client,
        headers,
        data["course_id"],
        {"studentIds": [data["student1_id"]]},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["totals"]["visitCount"] == 2
    assert payload["totals"]["studentCount"] == 1
    assert len(payload["byVisit"]) == 2
    assert len(payload["byStudent"]) == 1

    # Nhiều ca của nhiều sinh viên.
    response = await _post_summary(
        client,
        headers,
        data["course_id"],
        {"studentIds": [data["student1_id"], data["student2_id"]]},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["totals"]["visitCount"] == 4
    assert payload["totals"]["studentCount"] == 2
    assert len(payload["byStudent"]) == 2
    assert len(payload["byLesson"]) == 1

    # Lọc theo bài.
    response = await _post_summary(
        client,
        headers,
        data["course_id"],
        {"lessonIds": [data["lesson_id"]]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["totals"]["contentViewCount"] == 4


@pytest.mark.asyncio
async def test_summary_hides_dropped_students_by_default(client):
    data = await _seed_summary_data()
    async with SessionLocal() as db:
        await db.execute(
            update(Enrollment)
            .where(Enrollment.id == data["enrollment2_id"])
            .values(status="dropped")
        )
        await db.commit()

    token = await login(client, data["teacher_email"])
    headers = {"Authorization": f"Bearer {token}"}

    response = await _post_summary(client, headers, data["course_id"], {})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["totals"]["visitCount"] == 2
    assert payload["totals"]["studentCount"] == 1

    response = await _post_summary(
        client, headers, data["course_id"], {"includeDropped": True}
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["totals"]["visitCount"] == 4
    assert payload["totals"]["studentCount"] == 2


@pytest.mark.asyncio
async def test_heatmap_sums_selected_views(client):
    data = await _seed_summary_data()
    token = await login(client, data["teacher_email"])
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        f"/teacher/courses/{data['course_id']}/analytics/heatmap",
        headers=headers,
        json={"studentIds": [data["student1_id"]], "slideId": data["slide_id"]},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["slide"]["id"] == data["slide_id"]
    assert payload["slide"]["pdfUrl"].startswith("/media/assets/")
    assert len(payload["grid"]) == 24
    assert payload["onSlideSampleCount"] == 4
    assert payload["max"] == 4
    assert payload["grid"][12][12] == 4
    # Hai ca của học viên 1 đều đã phân tích bằng version hiện hành.
    assert payload["analyzedViewCount"] == 2
    assert payload["staleViewCount"] == 0


@pytest.mark.asyncio
async def test_heatmap_rejects_slide_of_other_course(client):
    data = await _seed_summary_data()
    token = await login(client, data["teacher_email"])
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        f"/teacher/courses/{data['course_id']}/analytics/heatmap",
        headers=headers,
        json={"slideId": str(uuid.uuid4())},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_heatmap_excludes_stale_analysis_version(client):
    data = await _seed_summary_data()
    stale_view_id = data["visits1"][0]["view_id"]
    async with SessionLocal() as db:
        view = await db.get(ContentView, stale_view_id)
        assert view is not None and view.heatmap_grid is not None
        view.analysis_version = "gaze-metrics-v6"
        await db.commit()

    token = await login(client, data["teacher_email"])
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        f"/teacher/courses/{data['course_id']}/analytics/heatmap",
        headers=headers,
        json={"studentIds": [data["student1_id"]], "slideId": data["slide_id"]},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    # Grid của view cũ không được cộng; chỉ còn view hiện hành (2 mẫu on-slide).
    assert payload["analyzedViewCount"] == 1
    assert payload["staleViewCount"] == 1
    assert payload["onSlideSampleCount"] == 2
    assert payload["max"] == 2
    assert payload["grid"][12][12] == 2


@pytest.mark.asyncio
async def test_heatmap_ignores_global_surface_and_lesson_filter(client):
    data = await _seed_summary_data()
    token = await login(client, data["teacher_email"])
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        f"/teacher/courses/{data['course_id']}/analytics/heatmap",
        headers=headers,
        json={
            "studentIds": [data["student1_id"]],
            "slideId": data["slide_id"],
            "surface": "quiz",
            "lessonIds": ["00000000-0000-0000-0000-000000000000"],
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    # Heatmap một slide không được bị filter surface/bài toàn cục vô hiệu hoá.
    assert payload["onSlideSampleCount"] == 4
    assert payload["max"] == 4
    assert payload["analyzedViewCount"] == 2


@pytest.mark.asyncio
async def test_heatmap_ready_but_incomplete_grid_is_stale(client):
    data = await _seed_summary_data()
    view_id = data["visits1"][0]["view_id"]
    async with SessionLocal() as db:
        view = await db.get(ContentView, view_id)
        assert view is not None
        view.analysis_status = "ready"
        view.analysis_version = metrics.ANALYSIS_VERSION
        view.heatmap_grid = []
        await db.commit()

    token = await login(client, data["teacher_email"])
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.post(
        f"/teacher/courses/{data['course_id']}/analytics/heatmap",
        headers=headers,
        json={"studentIds": [data["student1_id"]], "slideId": data["slide_id"]},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["analyzedViewCount"] == 1
    assert payload["staleViewCount"] == 1
    assert payload["onSlideSampleCount"] == 2


@pytest.mark.asyncio
async def test_heatmap_counts_never_analyzed_view_as_stale(client):
    data = await _seed_summary_data()
    pending_view_id = data["visits1"][0]["view_id"]
    async with SessionLocal() as db:
        view = await db.get(ContentView, pending_view_id)
        assert view is not None
        # View mới chưa phân tích: các cột dẫn xuất vẫn ở default (gaze_count=0,
        # grid rỗng) nhưng gaze thô đã tồn tại.
        view.analysis_status = "pending"
        view.analysis_version = "gaze-metrics-v3"
        view.gaze_count = 0
        view.on_slide_gaze_count = 0
        view.heatmap_grid = []
        await db.commit()

    token = await login(client, data["teacher_email"])
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        f"/teacher/courses/{data['course_id']}/analytics/heatmap",
        headers=headers,
        json={"studentIds": [data["student1_id"]], "slideId": data["slide_id"]},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["analyzedViewCount"] == 1
    assert payload["staleViewCount"] == 1
    assert payload["onSlideSampleCount"] == 2


@pytest.mark.asyncio
async def test_summary_and_heatmap_include_short_flag(client):
    data = await _seed_summary_data()
    visit_id = data["visits1"][0]["visit_id"]

    async with SessionLocal() as db:
        visit = await db.get(CourseVisit, visit_id)
        assert visit is not None
        session = (
            await db.execute(
                select(LearningSession)
                .where(LearningSession.course_visit_id == visit.id)
                .order_by(LearningSession.started_at)
                .limit(1)
            )
        ).scalar_one()
        grid = [[0 for _ in range(metrics.GRID_SIZE)] for _ in range(metrics.GRID_SIZE)]
        grid[0][0] = 1
        short_started = visit.started_at + timedelta(seconds=40)
        db.add(
            ContentView(
                session_id=session.id,
                slide_id=data["slide_id"],
                surface="lesson",
                sequence_no=1,
                started_at=short_started,
                ended_at=short_started + timedelta(milliseconds=250),
                tracked_duration_ms=50,
                gaze_count=1,
                on_slide_gaze_count=1,
                heatmap_grid=grid,
                analysis_status="ready",
                analysis_version=metrics.ANALYSIS_VERSION,
            )
        )
        await db.commit()

    token = await login(client, data["teacher_email"])
    headers = {"Authorization": f"Bearer {token}"}
    scope = {"visitIds": [visit_id]}

    # Mặc định: lượt ngắn vẫn được tính và chỉ được đánh dấu trong meta.
    response = await _post_summary(client, headers, data["course_id"], scope)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["totals"]["contentViewCount"] == 2
    assert payload["totals"]["trackedDurationMs"] == 250
    assert payload["meta"]["includeShort"] is True
    assert payload["meta"]["shortViewCount"] == 1
    assert payload["meta"]["minDwellMs"] == 1000

    response = await _post_summary(
        client, headers, data["course_id"], {**scope, "includeShort": False}
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["totals"]["contentViewCount"] == 1
    assert payload["totals"]["trackedDurationMs"] == 200
    assert payload["meta"]["includeShort"] is False
    assert payload["meta"]["shortViewCount"] == 1

    heatmap_url = f"/teacher/courses/{data['course_id']}/analytics/heatmap"
    heatmap_body = {**scope, "slideId": data["slide_id"]}
    response = await client.post(heatmap_url, headers=headers, json=heatmap_body)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["onSlideSampleCount"] == 3
    assert payload["grid"][0][0] == 1
    assert payload["analyzedViewCount"] == 2
    assert payload["staleViewCount"] == 0

    response = await client.post(
        heatmap_url,
        headers=headers,
        json={**heatmap_body, "includeShort": False},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["onSlideSampleCount"] == 2
    assert payload["grid"][0][0] == 0
    assert payload["analyzedViewCount"] == 1
    assert payload["staleViewCount"] == 0
