import uuid

import pytest

from app.db.session import SessionLocal
from app.models.course import (
    Course,
    CourseVersion,
    CourseVersionItem,
    CourseVersionModule,
    Lesson,
    LessonVersion,
)
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

    outline = await client.get(f"/api/courses/{ids['course_id']}", headers=headers)
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

    draft = await client.get(
        f"/teacher/courses/{ids['course_id']}/draft", headers=headers
    )
    assert draft.status_code == 200, draft.text
    assert len(draft.json()) == 1
    assert draft.json()[0]["lessons"][0]["id"] == ids["lesson_id"]

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
        lesson_version_id=ids["lesson_version_id"],
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

    teacher_token = await login(client, teacher_email)
    slides = await client.get(
        f"/teacher/lessons/{ids['lesson_id']}/slides",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert slides.status_code == 200, slides.text
    assert len(slides.json()) == 1
    assert slides.json()[0]["embeddingStatus"] == "none"

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


@pytest.mark.asyncio
async def test_teacher_slides_published_version_uses_published_slide_versions(client):
    """AOI editor phải đọc được slide của bản xuất bản, không lẫn bản nháp."""
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)

    published_slide = await seed_slide(
        course_id=ids["course_id"],
        lesson_id=ids["lesson_id"],
        lesson_version_id=ids["lesson_version_id"],
        teacher_id=teacher_id,
    )

    async with SessionLocal() as db:
        draft_version = CourseVersion(
            course_id=ids["course_id"],
            version_no=2,
            state="draft",
            title="Test Course",
            created_by=teacher_id,
        )
        db.add(draft_version)
        await db.flush()
        draft_module = CourseVersionModule(
            course_version_id=draft_version.id,
            title="Module 1",
            position=0,
        )
        db.add(draft_module)
        await db.flush()
        draft_lesson_version = LessonVersion(
            lesson_id=ids["lesson_id"],
            version_no=2,
            state="draft",
            title="Lesson 1",
            created_by=teacher_id,
        )
        db.add(draft_lesson_version)
        await db.flush()
        db.add(
            CourseVersionItem(
                course_version_id=draft_version.id,
                module_id=draft_module.id,
                lesson_id=ids["lesson_id"],
                lesson_version_id=draft_lesson_version.id,
                position=0,
            )
        )
        await db.commit()
        draft_lesson_version_id = draft_lesson_version.id

    draft_slide = await seed_slide(
        course_id=ids["course_id"],
        lesson_id=ids["lesson_id"],
        lesson_version_id=draft_lesson_version_id,
        teacher_id=teacher_id,
    )

    token = await login(client, teacher_email)
    headers = {"Authorization": f"Bearer {token}"}

    published = await client.get(
        f"/teacher/lessons/{ids['lesson_id']}/slides?version=published",
        headers=headers,
    )
    assert published.status_code == 200, published.text
    assert [item["slideVersionId"] for item in published.json()] == [
        published_slide["slide_version_id"]
    ]

    draft = await client.get(
        f"/teacher/lessons/{ids['lesson_id']}/slides?version=draft",
        headers=headers,
    )
    assert draft.status_code == 200, draft.text
    assert [item["slideVersionId"] for item in draft.json()] == [
        draft_slide["slide_version_id"]
    ]


@pytest.mark.asyncio
async def test_teacher_slides_published_version_requires_published_course(client):
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")

    async with SessionLocal() as db:
        course = Course(owner_id=teacher_id, created_by=teacher_id)
        db.add(course)
        await db.flush()
        version = CourseVersion(
            course_id=course.id,
            version_no=1,
            state="draft",
            title="Draft Course",
            created_by=teacher_id,
        )
        db.add(version)
        await db.flush()
        module = CourseVersionModule(
            course_version_id=version.id,
            title="Module 1",
            position=0,
        )
        db.add(module)
        await db.flush()
        lesson = Lesson(course_id=course.id, kind="lesson")
        db.add(lesson)
        await db.flush()
        lesson_version = LessonVersion(
            lesson_id=lesson.id,
            version_no=1,
            state="draft",
            title="Lesson 1",
            created_by=teacher_id,
        )
        db.add(lesson_version)
        await db.flush()
        db.add(
            CourseVersionItem(
                course_version_id=version.id,
                module_id=module.id,
                lesson_id=lesson.id,
                lesson_version_id=lesson_version.id,
                position=0,
            )
        )
        await db.commit()
        lesson_id = lesson.id

    token = await login(client, teacher_email)
    response = await client.get(
        f"/teacher/lessons/{lesson_id}/slides?version=published",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
