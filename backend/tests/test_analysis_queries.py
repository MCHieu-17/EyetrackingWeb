"""Export JSONL lấy trực tiếp từ gaze_samples + content_views."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.session import SessionLocal
from app.models.gaze import ContentView, GazeSample, LearningSession
from app.services.analysis.export import export_lines
from tests.conftest import create_user, seed_course


@pytest.mark.asyncio
async def test_analysis_export_manifest_and_flat_sample():
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    now = datetime.now(timezone.utc)

    async with SessionLocal() as db:
        learning_session = LearningSession(
            enrollment_id=ids["enrollment_id"],
            lesson_id=ids["lesson_id"],
            pipeline_version="test-v1",
            expires_at=now + timedelta(hours=1),
        )
        db.add(learning_session)
        await db.flush()
        view = ContentView(
            session_id=learning_session.id,
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
                slide_x=0.5,
                slide_y=0.5,
                aoi_label="SLIDE_AOI_1",
                aoi_codes=["SLIDE_AOI_1"],
                status="ok",
            )
        )
        await db.commit()

    lines = export_lines(ids["lesson_id"])
    manifest = json.loads(await anext(lines))
    sample = json.loads(await anext(lines))
    end = json.loads(await anext(lines))
    await lines.aclose()

    assert manifest["type"] == "manifest"
    assert manifest["lesson"]["id"] == ids["lesson_id"]
    assert sample["type"] == "sample"
    assert sample["aoiLabel"] == "SLIDE_AOI_1"
    assert sample["aoiCodes"] == ["SLIDE_AOI_1"]
    assert sample["slideX"] == 0.5
    assert "courseVersionId" not in sample
    assert end["type"] == "end"
