"""Query-count cho cập nhật quiz spec (P2).

Đo trực tiếp route function với dữ liệu seed thật, sau khi bản nháp đã được
tạo sẵn — nhờ vậy phép đo chỉ phản ánh đường cập nhật, không gồm clone nội
dung (vốn là hành vi hợp lệ của content service).
"""

import uuid

import pytest

from app.api.access import get_course_or_404
from app.api.routes.quiz_specs import update_quiz_spec
from app.db.session import SessionLocal, engine
from app.models.auth import User
from app.schemas.quiz import QuizAssignmentUpdate
from app.services import content
from tests.conftest import create_user, seed_quiz
from tests.query_counter import count_queries


@pytest.mark.asyncio
async def test_quiz_spec_update_query_count():
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_quiz(teacher_id=teacher_id, student_id=student_id)

    # Tạo sẵn course version nháp + lesson version nháp để không đo phần clone.
    async with SessionLocal() as db:
        teacher = await db.get(User, teacher_id)
        assert teacher is not None
        course = await get_course_or_404(db, ids["course_id"])
        _, item = await content.get_draft_item_for_lesson(
            db, course, ids["lesson_id"], teacher
        )
        await content.ensure_draft_lesson_version(db, item, teacher)
        await db.commit()

    async with SessionLocal() as db:
        teacher = await db.get(User, teacher_id)
        assert teacher is not None
        with count_queries(engine) as counter:
            result = await update_quiz_spec(
                ids["lesson_version_id"],
                QuizAssignmentUpdate(instructions="Hướng dẫn mới"),
                teacher,
                db,
            )

    assert result.instructions == "Hướng dẫn mới"
    assert result.status == "published"
    # 3 lookup + draft/item + lesson version nháp + quiz + 2 update
    # + 2 refresh + published check.
    assert counter.count == 12, counter.statements
    # Không còn selectin cho slides/versions/enrollments của course graph.
    assert not any("lesson_versions_slides" in sql for sql in counter.statements)
    assert not any("FROM slides" in sql for sql in counter.statements)
    assert not any("FROM enrollments" in sql for sql in counter.statements)
