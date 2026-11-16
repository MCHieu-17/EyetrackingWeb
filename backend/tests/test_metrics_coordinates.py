import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.aoi import Aoi
from app.models.gaze import ContentView, GazeSample, LearningSession, ViewLayout
from app.services import metrics
from tests.conftest import create_user, seed_course, seed_slide


@pytest.mark.asyncio
async def test_analysis_returns_one_priority_leaf_label():
    teacher_id = await create_user(
        email=f"coord-t-{uuid.uuid4().hex[:8]}@example.com", role="teacher"
    )
    student_id = await create_user(
        email=f"coord-s-{uuid.uuid4().hex[:8]}@example.com"
    )
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    slide_ids = await seed_slide(
        course_id=ids["course_id"],
        lesson_id=ids["lesson_id"],
        teacher_id=teacher_id,
    )
    now = datetime.now(timezone.utc)

    async with SessionLocal() as db:
        db.add_all(
            [
                Aoi(
                    slide_id=slide_ids["slide_id"],
                    code="img",
                    name="Image",
                    label="AOI_1",
                    geometry={"xMin": 0.1, "yMin": 0.1, "xMax": 0.9, "yMax": 0.9},
                    kind="image",
                ),
                Aoi(
                    slide_id=slide_ids["slide_id"],
                    code="text",
                    name="Thanh chát",
                    label="AOI_THANHCHAT",
                    geometry={"xMin": 0.2, "yMin": 0.2, "xMax": 0.8, "yMax": 0.8},
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
        view_id = view.id

    async with SessionLocal() as db:
        updated = await metrics.analyze_content_view(db, view_id)
        await db.commit()
        assert updated.on_slide_gaze_count == 1

    async with SessionLocal() as db:
        sample = (
            await db.execute(
                GazeSample.__table__.select().where(
                    GazeSample.content_view_id == view_id
                )
            )
        ).mappings().one()
        # Nhãn giáo viên giữ nguyên sau tiền tố SLIDE_.
        assert sample["aoi_label"] == "SLIDE_AOI_THANHCHAT"


@pytest.mark.asyncio
async def test_inside_slide_suppresses_ui_and_outside_uses_ui_name():
    teacher_id = await create_user(
        email=f"branch-t-{uuid.uuid4().hex[:8]}@example.com", role="teacher"
    )
    student_id = await create_user(
        email=f"branch-s-{uuid.uuid4().hex[:8]}@example.com"
    )
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    slide_ids = await seed_slide(
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
                    slide_id=slide_ids["slide_id"],
                    code="text",
                    name="Text",
                    label="AOI_1",
                    geometry={"xMin": 0, "yMin": 0, "xMax": 1, "yMax": 1},
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
            slide_rect={"left": 0.2, "top": 0, "width": 0.6, "height": 1},
            elements=[
                {
                    "code": header_code,
                    "xMin": 0,
                    "yMin": 0,
                    "xMax": 1,
                    "yMax": 1,
                }
            ],
        )
        db.add(layout)
        await db.flush()
        db.add_all(
            [
                GazeSample(
                    content_view_id=view.id,
                    layout_id=layout.id,
                    client_batch_id=uuid.uuid4(),
                    sequence=0,
                    event_time=now,
                    viewport_x=0.5,
                    viewport_y=0.5,
                    status="ok",
                ),
                GazeSample(
                    content_view_id=view.id,
                    layout_id=layout.id,
                    client_batch_id=uuid.uuid4(),
                    sequence=1,
                    event_time=now + timedelta(milliseconds=100),
                    viewport_x=0.1,
                    viewport_y=0.05,
                    status="ok",
                ),
            ]
        )
        await db.commit()
        view_id = view.id

    async with SessionLocal() as db:
        await metrics.analyze_content_view(db, view_id)
        await db.commit()

    async with SessionLocal() as db:
        samples = (
            await db.execute(
                select(GazeSample)
                .where(GazeSample.content_view_id == view_id)
                .order_by(GazeSample.sequence)
            )
        ).scalars().all()
        assert samples[0].aoi_label == "SLIDE_AOI_1"
        assert samples[1].aoi_label == "Thanh trên"


@pytest.mark.asyncio
async def test_missing_layout_does_not_identity_map():
    teacher_id = await create_user(
        email=f"missing-t-{uuid.uuid4().hex[:8]}@example.com", role="teacher"
    )
    student_id = await create_user(
        email=f"missing-s-{uuid.uuid4().hex[:8]}@example.com"
    )
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    slide_ids = await seed_slide(
        course_id=ids["course_id"],
        lesson_id=ids["lesson_id"],
        teacher_id=teacher_id,
    )
    now = datetime.now(timezone.utc)

    async with SessionLocal() as db:
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
        db.add(
            GazeSample(
                content_view_id=view.id,
                client_batch_id=uuid.uuid4(),
                sequence=0,
                event_time=now,
                viewport_x=0.5,
                viewport_y=0.5,
                status="ok",
            )
        )
        await db.commit()
        view_id = view.id

    async with SessionLocal() as db:
        updated = await metrics.analyze_content_view(db, view_id)
        await db.commit()
        assert updated.on_slide_gaze_count == 0

    async with SessionLocal() as db:
        sample = (
            await db.execute(
                GazeSample.__table__.select().where(
                    GazeSample.content_view_id == view_id
                )
            )
        ).mappings().one()
        assert sample["slide_x"] is None
        assert sample["slide_y"] is None
        assert sample["quality_flags"]["layout_missing"] is True
        assert sample["aoi_label"] == "UI_NO_LABEL"


@pytest.mark.asyncio
async def test_quiz_does_not_count_on_slide_and_keeps_ui_aoi():
    teacher_id = await create_user(
        email=f"quiz-t-{uuid.uuid4().hex[:8]}@example.com", role="teacher"
    )
    student_id = await create_user(
        email=f"quiz-s-{uuid.uuid4().hex[:8]}@example.com"
    )
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    now = datetime.now(timezone.utc)

    header_code = f"header-{uuid.uuid4().hex[:8]}"
    async with SessionLocal() as db:
        db.add(
            Aoi(
                ui_schema="reader-v1",
                code=header_code,
                name="Header",
                geometry={"selector": f"[data-aoi='{header_code}']"},
                kind="ui",
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
            slide_id=None,
            surface="quiz",
            sequence_no=0,
        )
        db.add(view)
        await db.flush()
        layout = ViewLayout(
            content_view_id=view.id,
            layout_no=0,
            slide_rect={},
            elements=[
                {
                    "code": header_code,
                    "xMin": 0,
                    "yMin": 0,
                    "xMax": 1,
                    "yMax": 0.1,
                }
            ],
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
                viewport_y=0.05,
                status="ok",
            )
        )
        await db.commit()
        view_id = view.id

    async with SessionLocal() as db:
        updated = await metrics.analyze_content_view(db, view_id)
        await db.commit()
        assert updated.on_slide_gaze_count == 0

    async with SessionLocal() as db:
        sample = (
            await db.execute(
                GazeSample.__table__.select().where(
                    GazeSample.content_view_id == view_id
                )
            )
        ).mappings().one()
        assert sample["aoi_label"] == "Header"
