import uuid

import pytest
from sqlalchemy import text

from app.models.media import SlideDocument
from app.services import embedding
from tests.conftest import (
    SessionLocal,
    create_user,
    seed_course,
    seed_slide,
)


async def _seed_slide_with_document(state: str, error: str | None = None):
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    slide = await seed_slide(
        course_id=ids["course_id"],
        lesson_id=ids["lesson_id"],
        lesson_version_id=ids["lesson_version_id"],
        teacher_id=teacher_id,
    )
    async with SessionLocal() as db:
        # content_tsv là generated column — không được đưa vào INSERT.
        await db.execute(
            text(
                """
                INSERT INTO slide_documents (
                    slide_version_id, pipeline_version, model_version,
                    transcript, embedding, ingestion_state, ingestion_error
                )
                VALUES (
                    :slide_version_id, 'rag-v2', 'qwen3-embedding-0.6b',
                    '', NULL, :state, :error
                )
                """
            ),
            {
                "slide_version_id": slide["slide_version_id"],
                "state": state,
                "error": error,
            },
        )
        await db.commit()
    return slide["slide_version_id"]


@pytest.mark.asyncio
async def test_mark_many_does_not_demote_ready_slides():
    """Job khác không được kéo slide vừa ready về pending."""
    slide_version_id = await _seed_slide_with_document("ready")

    async with SessionLocal() as db:
        await embedding._mark_many(db, [slide_version_id], embedding.PENDING)

    async with SessionLocal() as db:
        document = await db.get(SlideDocument, slide_version_id)
        assert document is not None
        assert document.ingestion_state == "ready"


@pytest.mark.asyncio
async def test_mark_failed_unready_keeps_ready_slides():
    """Batch lỗi không được ghi đè slide đã ingest xong."""
    slide_version_id = await _seed_slide_with_document("ready")

    async with SessionLocal() as db:
        await embedding._mark_failed_unready(
            db, [slide_version_id], "batch failed"
        )

    async with SessionLocal() as db:
        document = await db.get(SlideDocument, slide_version_id)
        assert document is not None
        assert document.ingestion_state == "ready"
        assert document.ingestion_error is None


@pytest.mark.asyncio
async def test_mark_failed_unready_marks_pending_slides():
    slide_version_id = await _seed_slide_with_document("pending")

    async with SessionLocal() as db:
        await embedding._mark_failed_unready(
            db, [slide_version_id], "batch failed"
        )

    async with SessionLocal() as db:
        document = await db.get(SlideDocument, slide_version_id)
        assert document is not None
        assert document.ingestion_state == "failed"
        assert document.ingestion_error == "batch failed"


@pytest.mark.asyncio
async def test_mark_failed_unready_keeps_specific_chatbot_error():
    """Lỗi cụ thể chatbot đã ghi (vd VLM) không bị lỗi batch ghi đè."""
    slide_version_id = await _seed_slide_with_document(
        "failed", "VLM tạm thời không khả dụng"
    )

    async with SessionLocal() as db:
        await embedding._mark_failed_unready(
            db, [slide_version_id], "batch failed"
        )

    async with SessionLocal() as db:
        document = await db.get(SlideDocument, slide_version_id)
        assert document is not None
        assert document.ingestion_state == "failed"
        assert document.ingestion_error == "VLM tạm thời không khả dụng"
