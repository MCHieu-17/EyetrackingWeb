"""Query-count cho cập nhật quiz spec (schema không versioning)."""

import uuid

import pytest

from app.api.routes.quiz_editor import update_quiz_spec
from app.db.session import SessionLocal, engine
from app.models.auth import User
from app.schemas.quiz import QuizAssignmentUpdate
from tests.conftest import create_user, seed_quiz
from tests.query_counter import count_queries


@pytest.mark.asyncio
async def test_quiz_spec_update_query_count():
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_quiz(teacher_id=teacher_id, student_id=student_id)

    async with SessionLocal() as db:
        teacher = await db.get(User, teacher_id)
        assert teacher is not None
        with count_queries(engine) as counter:
            result = await update_quiz_spec(
                ids["lesson_id"],
                QuizAssignmentUpdate(instructions="Hướng dẫn mới"),
                teacher,
                db,
            )

    assert result.instructions == "Hướng dẫn mới"
    assert result.status == "published"
    assert counter.count <= 6, counter.statements
    assert not any("course_versions" in sql for sql in counter.statements)
    assert not any("lesson_versions" in sql for sql in counter.statements)
