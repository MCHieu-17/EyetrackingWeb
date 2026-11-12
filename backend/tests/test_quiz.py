import uuid

import pytest

from app.models.course import Course
from tests.conftest import SessionLocal, create_user, login, seed_quiz


@pytest.mark.asyncio
async def test_quiz_flow(client):
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_quiz(teacher_id=teacher_id, student_id=student_id)
    token = await login(client, student_email)
    headers = {"Authorization": f"Bearer {token}"}

    spec = await client.get(
        f"/api/quiz-specs/{ids['lesson_version_id']}", headers=headers
    )
    assert spec.status_code == 200, spec.text
    assert spec.json()["questions"][0]["correctOptionIds"] == []

    attempt = await client.post(
        f"/api/lessons/{ids['lesson_id']}/attempts", headers=headers
    )
    assert attempt.status_code == 201, attempt.text
    attempt_id = attempt.json()["id"]

    attempts = await client.get(
        f"/api/lessons/{ids['lesson_id']}/attempts", headers=headers
    )
    assert attempts.status_code == 200, attempts.text
    assert len(attempts.json()) == 1

    submitted = await client.post(
        f"/api/attempts/{attempt_id}/submit",
        headers=headers,
        json={"answers": {"q1": ["a"]}},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["score"] == 1

    retry = await client.post(
        f"/api/attempts/{attempt_id}/retry", headers=headers
    )
    assert retry.status_code == 201, retry.text
    assert retry.json()["status"] == "in_progress"


@pytest.mark.asyncio
async def test_teacher_toggle_allow_retry_applies_to_published_quiz(client):
    """Bật/tắt làm lại phải có hiệu lực với sinh viên ngay, không cần publish lại."""
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_quiz(teacher_id=teacher_id, student_id=student_id)

    teacher_token = await login(client, teacher_email)
    student_token = await login(client, student_email)
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
    student_headers = {"Authorization": f"Bearer {student_token}"}

    # Tắt làm lại: sinh viên thấy cờ mới dù chưa publish lại.
    saved = await client.patch(
        f"/teacher/quiz-specs/{ids['lesson_version_id']}",
        headers=teacher_headers,
        json={"allowRetry": False},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["allowRetry"] is False

    spec = await client.get(
        f"/api/quiz-specs/{ids['lesson_version_id']}", headers=student_headers
    )
    assert spec.status_code == 200, spec.text
    assert spec.json()["allowRetry"] is False

    # Bật lại: sinh viên thấy cờ mới.
    saved = await client.patch(
        f"/teacher/quiz-specs/{ids['lesson_version_id']}",
        headers=teacher_headers,
        json={"allowRetry": True},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["allowRetry"] is True

    spec = await client.get(
        f"/api/quiz-specs/{ids['lesson_version_id']}", headers=student_headers
    )
    assert spec.status_code == 200, spec.text
    assert spec.json()["allowRetry"] is True


@pytest.mark.asyncio
async def test_teacher_toggle_allow_chatbot_applies_to_published_quiz(client):
    """Tắt chatbot khi làm bài phải có hiệu lực với sinh viên ngay."""
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_quiz(teacher_id=teacher_id, student_id=student_id)

    teacher_token = await login(client, teacher_email)
    student_token = await login(client, student_email)
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
    student_headers = {"Authorization": f"Bearer {student_token}"}

    saved = await client.patch(
        f"/teacher/quiz-specs/{ids['lesson_version_id']}",
        headers=teacher_headers,
        json={"allowChatbot": False},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["allowChatbot"] is False

    spec = await client.get(
        f"/api/quiz-specs/{ids['lesson_version_id']}", headers=student_headers
    )
    assert spec.status_code == 200, spec.text
    assert spec.json()["allowChatbot"] is False


@pytest.mark.asyncio
async def test_teacher_tree_marks_published_quiz_as_published(client):
    """Bản nháp trỏ tới lesson version đã xuất bản thì bài tập không còn cảnh báo nháp."""
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_quiz(teacher_id=teacher_id, student_id=student_id)

    token = await login(client, teacher_email)
    headers = {"Authorization": f"Bearer {token}"}

    tree = await client.get(
        f"/teacher/courses/{ids['course_id']}", headers=headers
    )
    assert tree.status_code == 200, tree.text
    quiz = next(
        lesson
        for module in tree.json()
        for lesson in module["lessons"]
        if lesson["kind"] == "quiz"
    )
    assert quiz["quizStatus"] == "published"


@pytest.mark.asyncio
async def test_quiz_visible_in_published_version_stays_published_while_drafting(client):
    """Sửa quiz tạo lesson version nháp nhưng sinh viên vẫn thấy bản đã publish."""
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_quiz(teacher_id=teacher_id, student_id=student_id)

    token = await login(client, teacher_email)
    headers = {"Authorization": f"Bearer {token}"}

    # Mở cây nội dung để tạo course version nháp (clone bản publish).
    tree = await client.get(
        f"/teacher/courses/{ids['course_id']}", headers=headers
    )
    assert tree.status_code == 200, tree.text

    # Sửa quiz không kèm status: backend clone lesson version sang nháp.
    saved = await client.patch(
        f"/teacher/quiz-specs/{ids['lesson_version_id']}",
        headers=headers,
        json={"instructions": "Hướng dẫn mới"},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["status"] == "published"

    tree = await client.get(
        f"/teacher/courses/{ids['course_id']}", headers=headers
    )
    assert tree.status_code == 200, tree.text
    quiz = next(
        lesson
        for module in tree.json()
        for lesson in module["lessons"]
        if lesson["kind"] == "quiz"
    )
    assert quiz["quizStatus"] == "published"

    # "Giao bài cho học viên" xuất bản course version nháp hiện tại.
    published = await client.patch(
        f"/teacher/quiz-specs/{quiz['quizId']}",
        headers=headers,
        json={"status": "published"},
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"

    async with SessionLocal() as db:
        course = await db.get(Course, ids["course_id"])
        assert course is not None
        assert course.published_version_id is not None
        assert course.published_version_id != ids["version_id"]
