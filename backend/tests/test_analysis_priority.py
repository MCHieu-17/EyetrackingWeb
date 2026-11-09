import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.aoi import AnalysisRun, AoiDefinition, AoiHit, AoiSet
from app.models.course import Slide, SlideVersion
from app.models.media import MediaAsset
from app.services import analysis
from tests.conftest import SessionLocal, create_user, login, seed_course


@pytest.mark.asyncio
async def test_slide_leaf_priority_prefers_text_over_image(client):
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)

    token = await login(client, student_email)
    headers = {"Authorization": f"Bearer {token}"}

    session_response = await client.post(
        "/api/learning-sessions",
        headers=headers,
        json={
            "enrollmentId": ids["enrollment_id"],
            "lessonId": ids["lesson_id"],
            "deviceFingerprint": "test-device",
            "viewportWidthPx": 1280,
            "viewportHeightPx": 720,
            "calibrationWidthPx": 1280,
            "calibrationHeightPx": 720,
            "devicePixelRatio": 1.0,
            "trackingConsent": True,
        },
    )
    assert session_response.status_code == 201, session_response.text
    session_id = session_response.json()["id"]

    presentation_response = await client.post(
        f"/api/learning-sessions/{session_id}/presentations",
        headers=headers,
        json={"surface": "lesson", "sequenceNo": 0},
    )
    assert presentation_response.status_code == 201, presentation_response.text
    presentation_id = presentation_response.json()["id"]

    layout_response = await client.post(
        f"/api/presentations/{presentation_id}/layouts",
        headers=headers,
        json={
            "sequenceNo": 0,
            "layoutGeneration": 0,
            "imageTransform": {"left": 0, "top": 0, "width": 1, "height": 1},
            "rects": [],
        },
    )
    assert layout_response.status_code == 201, layout_response.text
    layout_id = layout_response.json()["id"]

    batch_response = await client.post(
        f"/api/learning-sessions/{session_id}/gaze-batches",
        headers=headers,
        json={
            "batchId": str(uuid.uuid4()),
            "batchNo": 0,
            "presentationId": presentation_id,
            "layoutSnapshotId": layout_id,
            "sequenceStart": 0,
            "sequenceEnd": 0,
            "payloadHash": "a" * 64,
            "samples": [
                {
                    "sequence": 0,
                    "captureMonotonicNs": 1,
                    "eventTime": datetime.now(timezone.utc).isoformat(),
                    "viewportX": 0.5,
                    "viewportY": 0.5,
                    "status": "ok",
                    "qualityFlags": {},
                }
            ],
        },
    )
    assert batch_response.status_code == 200, batch_response.text

    async with SessionLocal() as db:
        asset = MediaAsset(
            course_id=ids["course_id"],
            storage_backend="local",
            object_key=f"test/{uuid.uuid4().hex}.pdf",
            sha256=uuid.uuid4().hex + uuid.uuid4().hex,
            mime_type="application/pdf",
            byte_size=1,
            state="ready",
            kind="normalized",
        )
        db.add(asset)
        await db.flush()
        slide = Slide(lesson_id=ids["lesson_id"])
        db.add(slide)
        await db.flush()
        slide_version = SlideVersion(
            slide_id=slide.id,
            revision_no=1,
            source_pdf_asset_id=asset.id,
            source_page=1,
            created_by=teacher_id,
        )
        db.add(slide_version)
        await db.flush()

        aoi_set = AoiSet(
            scope="slide",
            slide_version_id=slide_version.id,
            revision=1,
            state="draft",
            created_by=teacher_id,
        )
        db.add(aoi_set)
        await db.flush()
        db.add_all(
            [
                AoiDefinition(
                    aoi_set_id=aoi_set.id,
                    code="slide_1",
                    name="Slide 1",
                    geometry={"xMin": 0, "yMin": 0, "xMax": 1, "yMax": 1},
                    is_container=True,
                    kind="system",
                    is_active=True,
                ),
                AoiDefinition(
                    aoi_set_id=aoi_set.id,
                    code="slide_1_image_1",
                    name="ẢNH",
                    geometry={"xMin": 0.1, "yMin": 0.1, "xMax": 0.9, "yMax": 0.9},
                    is_container=False,
                    kind="image",
                    is_active=True,
                ),
                AoiDefinition(
                    aoi_set_id=aoi_set.id,
                    code="slide_1_text_1",
                    name="TEXT",
                    geometry={"xMin": 0.2, "yMin": 0.2, "xMax": 0.8, "yMax": 0.8},
                    is_container=False,
                    kind="text",
                    is_active=True,
                ),
                AoiDefinition(
                    aoi_set_id=aoi_set.id,
                    code="no_label",
                    name="Chưa đánh dấu",
                    geometry={},
                    is_container=False,
                    kind="system",
                    is_active=True,
                ),
            ]
        )
        await db.flush()
        aoi_set.state = "published"
        await db.flush()

        now = datetime.now(timezone.utc)
        run = AnalysisRun(
            session_id=session_id,
            presentation_id=presentation_id,
            aoi_set_id=aoi_set.id,
            from_time=now - timedelta(minutes=1),
            to_time=now + timedelta(minutes=1),
            algorithm_version="gaze-metrics-v1",
            config={},
            status="pending",
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        run_id = run.id

    async with SessionLocal() as db:
        await analysis.execute_run(db, run_id)

    async with SessionLocal() as db:
        hit_codes = set(
            (
                await db.execute(
                    select(AoiDefinition.code)
                    .join(AoiHit, AoiHit.definition_id == AoiDefinition.id)
                    .where(AoiHit.run_id == run_id)
                )
            )
            .scalars()
            .all()
        )
        assert "slide_1_text_1" in hit_codes
        assert "slide_1_image_1" not in hit_codes
