"""Upload PDF → background job → slides; thay PDF xóa slide cũ."""

from __future__ import annotations

import io
import uuid

import pytest
from pypdf import PdfWriter
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.background_job import BackgroundJob
from app.models.course import Slide
from app.services.content import process_slide_import
from tests.conftest import create_user, login, seed_course


def _pdf_bytes(pages: int) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


async def _upload(client, headers, lesson_id: str, pages: int) -> str:
    response = await client.post(
        f"/teacher/lessons/{lesson_id}/slides/upload",
        headers=headers,
        files={"file": ("slides.pdf", _pdf_bytes(pages), "application/pdf")},
    )
    assert response.status_code == 202, response.text
    return response.json()["jobId"]


async def _run_job(job_id: str) -> None:
    async with SessionLocal() as db:
        job = await db.get(BackgroundJob, job_id)
        assert job is not None
        job.status = "processing"
        await db.commit()
    await process_slide_import(job_id)


@pytest.mark.asyncio
async def test_slide_import_and_replace(client):
    teacher_email = f"upload-t-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"upload-s-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    token = await login(client, teacher_email)
    headers = {"Authorization": f"Bearer {token}"}

    first_job = await _upload(client, headers, ids["lesson_id"], 2)
    await _run_job(first_job)

    async with SessionLocal() as db:
        first_slides = (
            await db.execute(
                select(Slide.id)
                .where(Slide.lesson_id == ids["lesson_id"])
                .order_by(Slide.position)
            )
        ).scalars().all()
        job = await db.get(BackgroundJob, first_job)
        assert job is not None
        assert job.status == "ready"
        assert job.payload["page_count"] == 2
    assert len(first_slides) == 2

    second_job = await _upload(client, headers, ids["lesson_id"], 3)
    await _run_job(second_job)
    async with SessionLocal() as db:
        second_slides = (
            await db.execute(
                select(Slide.id)
                .where(Slide.lesson_id == ids["lesson_id"])
                .order_by(Slide.position)
            )
        ).scalars().all()
    assert len(second_slides) == 3
    assert set(first_slides).isdisjoint(second_slides)
