"""Lesson/module deletion must not leave PDF media assets or files behind."""

import uuid

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.media import MediaAsset
from tests.conftest import create_user, login, seed_course, seed_slide


@pytest.mark.asyncio
async def test_delete_lesson_removes_unreferenced_pdf_asset(client, monkeypatch):
    teacher_email = f"media-t-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"media-s-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    asset = await seed_slide(
        course_id=ids["course_id"],
        lesson_id=ids["lesson_id"],
        teacher_id=teacher_id,
    )

    deleted: list[tuple[str, str | None]] = []

    def fake_delete(key: str, backend: str | None = None) -> None:
        deleted.append((key, backend))

    monkeypatch.setattr("app.services.media_storage.delete_key", fake_delete)

    token = await login(client, teacher_email)
    response = await client.delete(
        f"/teacher/lessons/{ids['lesson_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    async with SessionLocal() as db:
        assert await db.get(MediaAsset, asset["asset_id"]) is None
    assert deleted and deleted[0][0].endswith(".pdf")
    assert deleted[0][1] == "local"


@pytest.mark.asyncio
async def test_delete_module_removes_pdf_assets_of_every_lesson(client, monkeypatch):
    teacher_email = f"media-t-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"media-s-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    asset = await seed_slide(
        course_id=ids["course_id"],
        lesson_id=ids["lesson_id"],
        teacher_id=teacher_id,
    )

    deleted: list[str] = []
    monkeypatch.setattr(
        "app.services.media_storage.delete_key",
        lambda key, backend=None: deleted.append(key),
    )

    token = await login(client, teacher_email)
    response = await client.delete(
        f"/teacher/modules/{ids['module_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    async with SessionLocal() as db:
        assert await db.get(MediaAsset, asset["asset_id"]) is None
        assert (
            await db.execute(select(MediaAsset.id).where(MediaAsset.id == asset["asset_id"]))
        ).first() is None
    assert deleted and deleted[0].endswith(".pdf")
