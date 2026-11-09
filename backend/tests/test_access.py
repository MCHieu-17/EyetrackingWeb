import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.access import (
    get_lesson_viewable,
    get_lesson_with_course,
    get_viewable_lesson,
)
from app.models.course import Course, Lesson


class _FakeDB:
    """DB tối thiểu: trả lesson, không trả course."""

    def __init__(self, lesson: Lesson):
        self.lesson = lesson

    async def get(self, model, ident, options=None):
        if model is Lesson:
            return self.lesson
        if model is Course:
            return None
        raise AssertionError(f"unexpected model: {model}")


def _lesson_without_course() -> Lesson:
    return Lesson(
        id=str(uuid.uuid4()),
        course_id=str(uuid.uuid4()),
        kind="lesson",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("helper", [get_viewable_lesson, get_lesson_viewable])
async def test_viewable_lesson_missing_course_is_403(helper):
    lesson = _lesson_without_course()
    db = _FakeDB(lesson)
    user = SimpleNamespace(role_codes=[])

    with pytest.raises(HTTPException) as exc_info:
        await helper(db, lesson.id, user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Không có quyền"


@pytest.mark.asyncio
async def test_get_lesson_with_course_missing_course_is_404():
    lesson = _lesson_without_course()
    db = _FakeDB(lesson)

    with pytest.raises(HTTPException) as exc_info:
        await get_lesson_with_course(db, lesson.id)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Không tìm thấy khóa học"
