"""Query-count và hành vi cho đường truy cập media/AOI (P2).

Các test này đo trực tiếp helper service-level để tránh nhiễu từ auth/rate
limit của request HTTP, nhưng vẫn dùng dữ liệu seed thật trong database.
"""

import uuid

import pytest
from fastapi import HTTPException

from app.api.routes.media import _get_asset_for_user
from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.models.auth import User
from app.models.media import MediaAsset
from app.services.aoi.access import _slide_version_course
from tests.conftest import create_user, login, seed_course, seed_slide
from tests.query_counter import count_queries


async def _seed_media_course():
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    slide_ids = await seed_slide(
        course_id=ids["course_id"],
        lesson_id=ids["lesson_id"],
        lesson_version_id=ids["lesson_version_id"],
        teacher_id=teacher_id,
    )
    return teacher_id, student_id, ids, slide_ids


@pytest.mark.asyncio
async def test_media_asset_access_queries_for_enrolled_student():
    _, student_id, _, slide_ids = await _seed_media_course()

    async with SessionLocal() as db:
        user = await db.get(User, student_id)
        assert user is not None
        with count_queries(engine) as counter:
            asset = await _get_asset_for_user(db, slide_ids["asset_id"], user)

    assert asset.id == slide_ids["asset_id"]
    # asset + course + enrollment + published check
    assert counter.count == 4, counter.statements


@pytest.mark.asyncio
async def test_media_asset_access_queries_for_course_owner():
    teacher_id, _, _, slide_ids = await _seed_media_course()

    async with SessionLocal() as db:
        user = await db.get(User, teacher_id)
        assert user is not None
        with count_queries(engine) as counter:
            asset = await _get_asset_for_user(db, slide_ids["asset_id"], user)

    assert asset.id == slide_ids["asset_id"]
    # asset + course; owner check không cần query thêm
    assert counter.count == 2, counter.statements


@pytest.mark.asyncio
async def test_media_asset_missing_is_404():
    _, student_id, _, _ = await _seed_media_course()

    async with SessionLocal() as db:
        user = await db.get(User, student_id)
        assert user is not None
        with pytest.raises(HTTPException) as exc_info:
            await _get_asset_for_user(db, str(uuid.uuid4()), user)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Không tìm thấy file"


@pytest.mark.asyncio
async def test_media_asset_outsider_is_403():
    _, _, _, slide_ids = await _seed_media_course()
    outsider_email = f"outsider-{uuid.uuid4().hex[:8]}@example.com"
    outsider_id = await create_user(email=outsider_email)

    async with SessionLocal() as db:
        user = await db.get(User, outsider_id)
        assert user is not None
        with pytest.raises(HTTPException) as exc_info:
            await _get_asset_for_user(db, slide_ids["asset_id"], user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Không có quyền"


@pytest.mark.asyncio
async def test_slide_version_course_query_count():
    _, _, _, slide_ids = await _seed_media_course()

    async with SessionLocal() as db:
        with count_queries(engine) as counter:
            slide_version, slide, lesson, course = await _slide_version_course(
                db, slide_ids["slide_version_id"]
            )

    assert slide_version.id == slide_ids["slide_version_id"]
    assert slide.id == slide_ids["slide_id"]
    assert lesson.id
    assert course.id
    # slide_version + slide + lesson + course, không selectin versions/slides
    assert counter.count == 4, counter.statements


@pytest.mark.asyncio
async def test_local_media_uses_x_accel_redirect(client):
    """File local do nginx phục vụ, backend chỉ kiểm tra quyền + trả header."""
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
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
    target = settings.media_path / object_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"%PDF-1.4\n")

    token = await login(client, student_email)
    response = await client.get(
        f"/media/assets/{slide_ids['asset_id']}/file",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    assert response.headers["x-accel-redirect"].startswith("/_protected_media/")
    assert response.headers["accept-ranges"] == "bytes"
    assert response.content == b""
