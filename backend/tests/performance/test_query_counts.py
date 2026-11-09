"""Query-count regression tests cho các endpoint nóng (P4 harness).

Mỗi test đăng nhập, gọi endpoint một lần để làm nóng pool, rồi đếm số câu SQL
phát ra trong lần gọi thứ hai. Baseline được ghi nhận từ implementation hiện
tại trên nhánh ``cleanup/integration``; P1–P3 sẽ hạ dần các hằng số này khi bỏ
được query thừa.

Lưu ý: số đếm bao gồm cả query xác thực (User + roles) và mọi query phát
sinh bên trong request, nên phản ánh đúng chi phí DB thực tế của endpoint.

Chạy riêng:

    TEST_DATABASE_URL=... backend/.venv/bin/pytest -q backend/tests/performance
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

import pytest

from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.models.media import MediaAsset
from tests.conftest import create_user, login, seed_course, seed_slide
from tests.query_counter import QueryCounter, count_queries

pytestmark = pytest.mark.performance

# Baseline ghi nhận ngày 2026-11-09 trên cleanup/integration (bao gồm auth).
TEACHER_COURSES_MAX_QUERIES = 6
COURSE_STUDENTS_MAX_QUERIES = 9
GAZE_BATCH_MAX_QUERIES = 14
MEDIA_ASSET_MAX_QUERIES = 17


def _assert_budget(counter: QueryCounter, budget: int, label: str) -> None:
    assert counter.count <= budget, (
        f"{label}: {counter.count} queries > budget {budget}\n" + "\n".join(counter.statements)
    )


def _sample(sequence: int) -> dict:
    return {
        "sequence": sequence,
        "captureMonotonicNs": sequence * 1_000_000,
        "eventTime": datetime.now(timezone.utc).isoformat(),
        "viewportX": 0.5,
        "viewportY": 0.5,
        "status": "ok",
        "qualityFlags": {},
    }


def _payload_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def _seed_teacher_and_student() -> tuple[str, str, str, dict[str, str]]:
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    return teacher_email, student_email, teacher_id, ids


@pytest.mark.asyncio
async def test_teacher_courses_query_count(client):
    teacher_email, _, _, _ = await _seed_teacher_and_student()
    token = await login(client, teacher_email)
    headers = {"Authorization": f"Bearer {token}"}

    warmup = await client.get("/teacher/courses", headers=headers)
    assert warmup.status_code == 200, warmup.text

    with count_queries(engine) as counter:
        response = await client.get("/teacher/courses", headers=headers)

    assert response.status_code == 200, response.text
    _assert_budget(counter, TEACHER_COURSES_MAX_QUERIES, "GET /teacher/courses")


@pytest.mark.asyncio
async def test_course_students_query_count(client):
    teacher_email, _, teacher_id, ids = await _seed_teacher_and_student()
    # Seed một slide để exercise cả nhánh metrics/mastery của endpoint.
    await seed_slide(
        course_id=ids["course_id"],
        lesson_id=ids["lesson_id"],
        lesson_version_id=ids["lesson_version_id"],
        teacher_id=teacher_id,
    )
    token = await login(client, teacher_email)
    headers = {"Authorization": f"Bearer {token}"}
    path = f"/teacher/courses/{ids['course_id']}/students"

    warmup = await client.get(path, headers=headers)
    assert warmup.status_code == 200, warmup.text

    with count_queries(engine) as counter:
        response = await client.get(path, headers=headers)

    assert response.status_code == 200, response.text
    _assert_budget(counter, COURSE_STUDENTS_MAX_QUERIES, f"GET {path}")


@pytest.mark.asyncio
async def test_gaze_batch_query_count(client):
    _, student_email, _, ids = await _seed_teacher_and_student()
    token = await login(client, student_email)
    headers = {"Authorization": f"Bearer {token}"}

    session_response = await client.post(
        "/api/learning-sessions",
        headers=headers,
        json={
            "enrollmentId": ids["enrollment_id"],
            "lessonId": ids["lesson_id"],
            "deviceFingerprint": "perf-device",
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
        json={"surface": "quiz", "sequenceNo": 0},
    )
    assert presentation_response.status_code == 201, presentation_response.text
    presentation_id = presentation_response.json()["id"]

    # Batch 0 làm nóng pool; batch 1 là lần được đếm (cùng nhánh xử lý).
    warmup = await client.post(
        f"/api/learning-sessions/{session_id}/gaze-batches",
        headers=headers,
        json={
            "batchId": str(uuid.uuid4()),
            "batchNo": 0,
            "presentationId": presentation_id,
            "sequenceStart": 0,
            "sequenceEnd": 1,
            "payloadHash": _payload_hash("warmup"),
            "samples": [_sample(0), _sample(1)],
        },
    )
    assert warmup.status_code == 200, warmup.text

    with count_queries(engine) as counter:
        response = await client.post(
            f"/api/learning-sessions/{session_id}/gaze-batches",
            headers=headers,
            json={
                "batchId": str(uuid.uuid4()),
                "batchNo": 1,
                "presentationId": presentation_id,
                "sequenceStart": 2,
                "sequenceEnd": 3,
                "payloadHash": _payload_hash("measured"),
                "samples": [_sample(2), _sample(3)],
            },
        )

    assert response.status_code == 200, response.text
    assert response.json()["stored"] == 2
    _assert_budget(
        counter,
        GAZE_BATCH_MAX_QUERIES,
        f"POST /api/learning-sessions/{session_id}/gaze-batches",
    )


@pytest.mark.asyncio
async def test_media_asset_file_query_count(client):
    _, student_email, teacher_id, ids = await _seed_teacher_and_student()
    slide_ids = await seed_slide(
        course_id=ids["course_id"],
        lesson_id=ids["lesson_id"],
        lesson_version_id=ids["lesson_version_id"],
        teacher_id=teacher_id,
    )

    async with SessionLocal() as db:
        asset = await db.get(MediaAsset, slide_ids["asset_id"])
        assert asset is not None
        object_key = asset.object_key

    file_path = settings.media_path / object_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(b"%PDF-1.4\n% perf test\n")

    token = await login(client, student_email)
    headers = {"Authorization": f"Bearer {token}"}
    path = f"/media/assets/{slide_ids['asset_id']}/file"

    warmup = await client.get(path, headers=headers)
    assert warmup.status_code == 200, warmup.text

    with count_queries(engine) as counter:
        response = await client.get(path, headers=headers)

    assert response.status_code == 200, response.text
    _assert_budget(counter, MEDIA_ASSET_MAX_QUERIES, f"GET {path}")
