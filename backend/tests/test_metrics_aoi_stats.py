"""Thống kê dẫn xuất `content_views.aoi_stats` theo nhãn AOI."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.session import SessionLocal
from app.models.aoi import Aoi
from app.models.gaze import ContentView, GazeSample, LearningSession, ViewLayout
from app.services import metrics
from tests.conftest import create_user, seed_course, seed_slide


async def _seed_view_with_samples() -> str:
    teacher_id = await create_user(
        email=f"stats-t-{uuid.uuid4().hex[:8]}@example.com", role="teacher"
    )
    student_id = await create_user(
        email=f"stats-s-{uuid.uuid4().hex[:8]}@example.com"
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
                    "yMax": 0.1,
                }
            ],
        )
        db.add(layout)
        await db.flush()

        def sample(sequence: int, at_ms: int, *, status: str, x: float, y: float):
            return GazeSample(
                content_view_id=view.id,
                layout_id=layout.id,
                client_batch_id=uuid.uuid4(),
                sequence=sequence,
                event_time=now + timedelta(milliseconds=at_ms),
                viewport_x=x if status == "ok" else None,
                viewport_y=y if status == "ok" else None,
                status=status,
            )

        db.add_all(
            [
                # Trong slide, AOI text.
                sample(0, 0, status="ok", x=0.5, y=0.5),
                # Ngoài slide, rơi vào header UI.
                sample(1, 100, status="ok", x=0.1, y=0.05),
                # Trong slide; 200ms từ mẫu UI trước đó.
                sample(2, 300, status="ok", x=0.5, y=0.5),
                # Mất dấu, không cộng thời gian.
                sample(3, 400, status="no_face", x=0.5, y=0.5),
                # Hồi phục sau no_face; không cộng khoảng 200ms.
                sample(4, 500, status="ok", x=0.5, y=0.5),
            ]
        )
        await db.commit()
        return view.id


@pytest.mark.asyncio
async def test_aoi_stats_accumulates_dwell_and_sample_counts():
    view_id = await _seed_view_with_samples()

    async with SessionLocal() as db:
        updated = await metrics.analyze_content_view(db, view_id)
        await db.commit()
        assert updated.analysis_version == "gaze-metrics-v6"
        # 100ms UI + 200ms slide; khoảng no_face không được cộng.
        assert updated.tracked_duration_ms == 300
        assert updated.aoi_stats == {
            "SLIDE_AOI_THANHCHAT": {"ms": 200, "samples": 3},
            "Thanh trên": {"ms": 100, "samples": 1},
        }
        total = sum(item["ms"] for item in updated.aoi_stats.values())
        samples = sum(item["samples"] for item in updated.aoi_stats.values())
        assert total == updated.tracked_duration_ms
        assert samples == 4
