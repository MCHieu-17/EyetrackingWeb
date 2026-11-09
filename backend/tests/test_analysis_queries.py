"""Query-count guard cho analysis manifest/export (P3).

Manifest chỉ cần một loạt ``db.get`` theo khóa chính; các quan hệ selectin
(``AoiSet.definitions``, ``LearningSession.presentations``,
``Course.versions``/``enrollments``, ``Enrollment.course``) phải được
raiseload để không phát sinh query thừa.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.session import SessionLocal, engine
from tests.conftest import create_user, seed_course
from tests.query_counter import count_queries


@pytest.mark.asyncio
async def test_analysis_manifest_query_count(client):
    from app.models.aoi import AnalysisRun, AoiSet
    from app.models.gaze import LearningSession
    from app.services.analysis.export import export_lines

    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)

    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        aoi_set = AoiSet(
            scope="ui",
            ui_schema_version=f"reader-{uuid.uuid4().hex[:8]}",
            revision=1,
            state="published",
            created_by=teacher_id,
        )
        db.add(aoi_set)
        await db.flush()
        learning_session = LearningSession(
            enrollment_id=ids["enrollment_id"],
            course_version_item_id=ids["item_id"],
            pipeline_version="test-v1",
            expires_at=now + timedelta(hours=1),
        )
        db.add(learning_session)
        await db.flush()
        run = AnalysisRun(
            session_id=learning_session.id,
            aoi_set_id=aoi_set.id,
            from_time=now - timedelta(minutes=5),
            to_time=now,
            algorithm_version="gaze-metrics-v1",
            status="completed",
        )
        db.add(run)
        await db.commit()
        run_id = run.id

    with count_queries(engine) as counter:
        lines = export_lines(run_id)
        first = await anext(lines)
        await lines.aclose()

    assert '"type": "manifest"' in first
    # run + session + enrollment + item + version + course + lesson
    # + lesson version + aoi set + definitions + presentations + layouts = 12.
    assert counter.count <= 14, counter.statements
