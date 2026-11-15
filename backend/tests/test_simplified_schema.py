"""Đảm bảo schema 24 bảng, cascade và pipeline gaze → AOI → metrics."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, text

from app.db.session import SessionLocal, engine
from app.models.aoi import Aoi
from app.models.course import Lesson, Slide
from app.models.gaze import ContentView, GazeSample, LearningSession, ViewLayout
from app.services import metrics
from tests.conftest import create_user, seed_course, seed_slide


@pytest.mark.asyncio
async def test_schema_has_24_core_tables():
    async with engine.connect() as conn:
        count = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM pg_tables WHERE schemaname = 'public' "
                    "AND tablename <> 'schema_migrations'"
                )
            )
        ).scalar_one()
    assert count == 24


@pytest.mark.asyncio
async def test_slide_delete_cascades_gaze_layout_metrics_aois():
    teacher_id = await create_user(
        email=f"cascade-t-{uuid.uuid4().hex[:8]}@example.com", role="teacher"
    )
    student_id = await create_user(
        email=f"cascade-s-{uuid.uuid4().hex[:8]}@example.com"
    )
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    slide_ids = await seed_slide(
        course_id=ids["course_id"], lesson_id=ids["lesson_id"], teacher_id=teacher_id
    )
    now = datetime.now(timezone.utc)

    async with SessionLocal() as db:
        db.add(
            Aoi(
                slide_id=slide_ids["slide_id"],
                code="text",
                name="Text",
                geometry={"xMin": 0.1, "yMin": 0.1, "xMax": 0.9, "yMax": 0.9},
                kind="text",
            )
        )
        session = LearningSession(
            enrollment_id=ids["enrollment_id"],
            lesson_id=ids["lesson_id"],
            expires_at=now + timedelta(hours=1),
        )
        db.add(session)
        await db.flush()
        view = ContentView(
            session_id=session.id,
            slide_id=slide_ids["slide_id"],
            surface="lesson",
            sequence_no=0,
        )
        db.add(view)
        await db.flush()
        layout = ViewLayout(
            content_view_id=view.id,
            layout_no=0,
            slide_rect={"left": 0, "top": 0, "width": 1, "height": 1},
        )
        db.add(layout)
        await db.flush()
        db.add(
            GazeSample(
                content_view_id=view.id,
                layout_id=layout.id,
                client_batch_id=uuid.uuid4(),
                sequence=0,
                event_time=now,
                viewport_x=0.5,
                viewport_y=0.5,
                status="ok",
            )
        )
        await db.commit()
        view_id, layout_id = view.id, layout.id

    async with SessionLocal() as db:
        slide = await db.get(Slide, slide_ids["slide_id"])
        assert slide is not None
        await db.delete(slide)
        await db.commit()

    async with SessionLocal() as db:
        assert await db.get(ContentView, view_id) is None
        assert await db.get(ViewLayout, layout_id) is None
        assert (
            await db.execute(
                select(func.count()).select_from(GazeSample).where(
                    GazeSample.content_view_id == view_id
                )
            )
        ).scalar_one() == 0
        assert (
            await db.execute(
                select(func.count()).select_from(Aoi).where(
                    Aoi.slide_id == slide_ids["slide_id"]
                )
            )
        ).scalar_one() == 0


@pytest.mark.asyncio
async def test_analysis_maps_sample_to_aoi_and_metrics():
    teacher_id = await create_user(
        email=f"map-t-{uuid.uuid4().hex[:8]}@example.com", role="teacher"
    )
    student_id = await create_user(
        email=f"map-s-{uuid.uuid4().hex[:8]}@example.com"
    )
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    slide_ids = await seed_slide(
        course_id=ids["course_id"], lesson_id=ids["lesson_id"], teacher_id=teacher_id
    )
    now = datetime.now(timezone.utc)

    async with SessionLocal() as db:
        db.add_all(
            [
                Aoi(
                    slide_id=slide_ids["slide_id"],
                    code="text",
                    name="Text",
                    label="AOI_1",
                    geometry={"xMin": 0.1, "yMin": 0.1, "xMax": 0.9, "yMax": 0.9},
                    kind="text",
                ),
                Aoi(
                    slide_id=slide_ids["slide_id"],
                    code="no_label",
                    name="Chưa đánh dấu",
                    geometry={},
                    kind="system",
                ),
            ]
        )
        session = LearningSession(
            enrollment_id=ids["enrollment_id"],
            lesson_id=ids["lesson_id"],
            expires_at=now + timedelta(hours=1),
        )
        db.add(session)
        await db.flush()
        view = ContentView(
            session_id=session.id,
            slide_id=slide_ids["slide_id"],
            surface="lesson",
            sequence_no=0,
        )
        db.add(view)
        await db.flush()
        layout = ViewLayout(
            content_view_id=view.id,
            layout_no=0,
            slide_rect={"left": 0, "top": 0, "width": 1, "height": 1},
        )
        db.add(layout)
        await db.flush()
        batch = uuid.uuid4()
        db.add_all(
            [
                GazeSample(
                    content_view_id=view.id,
                    layout_id=layout.id,
                    client_batch_id=batch,
                    sequence=0,
                    event_time=now,
                    viewport_x=0.5,
                    viewport_y=0.5,
                    status="ok",
                ),
                GazeSample(
                    content_view_id=view.id,
                    layout_id=layout.id,
                    client_batch_id=batch,
                    sequence=1,
                    event_time=now + timedelta(milliseconds=100),
                    viewport_x=0.5,
                    viewport_y=0.5,
                    status="ok",
                ),
            ]
        )
        await db.commit()
        view_id = view.id

    async with SessionLocal() as db:
        updated = await metrics.analyze_content_view(db, view_id)
        await db.commit()
        assert updated.analysis_status == "ready"
        assert updated.gaze_count == 2
        assert updated.on_slide_gaze_count == 2
        assert updated.tracked_duration_ms == 100
        assert updated.fixation_count == 1

    async with SessionLocal() as db:
        samples = (
            await db.execute(
                select(GazeSample).where(GazeSample.content_view_id == view_id)
            )
        ).scalars().all()
        assert all(sample.slide_x == 0.5 for sample in samples)
        assert all(sample.aoi_label == "SLIDE_AOI_1" for sample in samples)
        assert all(sample.aoi_codes == ["SLIDE_AOI_1"] for sample in samples)


@pytest.mark.asyncio
async def test_lesson_delete_cascades_slides_and_sessions():
    teacher_id = await create_user(
        email=f"lesson-t-{uuid.uuid4().hex[:8]}@example.com", role="teacher"
    )
    student_id = await create_user(
        email=f"lesson-s-{uuid.uuid4().hex[:8]}@example.com"
    )
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    await seed_slide(
        course_id=ids["course_id"], lesson_id=ids["lesson_id"], teacher_id=teacher_id
    )
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        db.add(
            LearningSession(
                enrollment_id=ids["enrollment_id"],
                lesson_id=ids["lesson_id"],
                expires_at=now + timedelta(hours=1),
            )
        )
        await db.commit()

    async with SessionLocal() as db:
        lesson = await db.get(Lesson, ids["lesson_id"])
        assert lesson is not None
        await db.delete(lesson)
        await db.commit()

    async with SessionLocal() as db:
        assert await db.get(Lesson, ids["lesson_id"]) is None
        assert (
            await db.execute(
                select(func.count()).select_from(Slide).where(
                    Slide.lesson_id == ids["lesson_id"]
                )
            )
        ).scalar_one() == 0
        assert (
            await db.execute(
                select(func.count()).select_from(LearningSession).where(
                    LearningSession.lesson_id == ids["lesson_id"]
                )
            )
        ).scalar_one() == 0
