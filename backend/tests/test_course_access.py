import uuid

import pytest

from tests.conftest import create_user, login, seed_course, seed_slide


@pytest.mark.asyncio
async def test_enrolled_student_can_read_course(client):
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)

    token = await login(client, student_email)
    headers = {"Authorization": f"Bearer {token}"}

    enrollments = await client.get("/api/me/enrollments", headers=headers)
    assert enrollments.status_code == 200, enrollments.text
    assert any(
        item["course"]["id"] == ids["course_id"] for item in enrollments.json()
    )

    outline = await client.get(
        f"/api/courses/{ids['course_id']}", headers=headers
    )
    assert outline.status_code == 200, outline.text
    data = outline.json()
    assert data["id"] == ids["course_id"]
    assert data["modules"][0]["lessons"][0]["id"] == ids["lesson_id"]


@pytest.mark.asyncio
async def test_teacher_course_dashboard_queries(client):
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)

    token = await login(client, teacher_email)
    headers = {"Authorization": f"Bearer {token}"}

    courses = await client.get("/teacher/courses", headers=headers)
    assert courses.status_code == 200, courses.text
    assert any(item["id"] == ids["course_id"] for item in courses.json())

    tree = await client.get(
        f"/teacher/courses/{ids['course_id']}/draft", headers=headers
    )
    assert tree.status_code == 200, tree.text
    assert len(tree.json()) == 1
    assert tree.json()[0]["lessons"][0]["id"] == ids["lesson_id"]

    students = await client.get(
        f"/teacher/courses/{ids['course_id']}/students", headers=headers
    )
    assert students.status_code == 200, students.text
    assert students.json()[0]["id"] == student_id

    slides = await client.get(
        f"/teacher/lessons/{ids['lesson_id']}/slides", headers=headers
    )
    assert slides.status_code == 200, slides.text
    assert slides.json() == []


@pytest.mark.asyncio
async def test_lesson_contents_with_slide(client):
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    await seed_slide(
        course_id=ids["course_id"],
        lesson_id=ids["lesson_id"],
        teacher_id=teacher_id,
    )

    student_token = await login(client, student_email)
    outline = await client.get(
        f"/api/courses/{ids['course_id']}",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert outline.status_code == 200, outline.text
    assert outline.json()["modules"][0]["lessons"][0]["slideCount"] == 1

    contents = await client.get(
        f"/api/lessons/{ids['lesson_id']}/contents",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert contents.status_code == 200, contents.text
    assert len(contents.json()) == 1
    assert contents.json()[0]["pdfUrl"]
    assert contents.json()[0]["id"]

    teacher_token = await login(client, teacher_email)
    slides = await client.get(
        f"/teacher/lessons/{ids['lesson_id']}/slides",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert slides.status_code == 200, slides.text
    assert len(slides.json()) == 1
    assert slides.json()[0]["embeddingStatus"] == "ready"

    students = await client.get(
        f"/teacher/courses/{ids['course_id']}/students",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert students.status_code == 200, students.text
    assert students.json()[0]["lessons"][0]["mastery"] == 0.0


@pytest.mark.asyncio
async def test_non_enrolled_student_cannot_read_course(client):
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    outsider_email = f"outsider-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    await create_user(email=outsider_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)

    token = await login(client, outsider_email)
    response = await client.get(
        f"/api/lessons/{ids['lesson_id']}/contents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
