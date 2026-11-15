"""Access control cho API AOI hiện hành."""

import uuid

import pytest

from tests.conftest import create_user, login, seed_course, seed_slide


@pytest.mark.asyncio
async def test_aoi_list_requires_manage_access_to_slide(client):
    owner_email = f"owner-{uuid.uuid4().hex[:8]}@example.com"
    other_email = f"other-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    owner_id = await create_user(email=owner_email, role="teacher")
    await create_user(email=other_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=owner_id, student_id=student_id)
    slide = await seed_slide(
        course_id=ids["course_id"],
        lesson_id=ids["lesson_id"],
        teacher_id=owner_id,
    )

    owner_token = await login(client, owner_email)
    owner_response = await client.get(
        "/api/aois",
        params={"slideId": slide["slide_id"]},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert owner_response.status_code == 200, owner_response.text
    assert owner_response.json()[0]["slideId"] == slide["slide_id"]

    other_token = await login(client, other_email)
    denied = await client.get(
        "/api/aois",
        params={"slideId": slide["slide_id"]},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert denied.status_code == 403

    student_token = await login(client, student_email)
    forbidden = await client.get(
        "/api/aois",
        params={"slideId": slide["slide_id"]},
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_ui_aoi_list_is_teacher_admin_only(client):
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    await create_user(email=teacher_email, role="teacher")
    await create_user(email=student_email)

    teacher_token = await login(client, teacher_email)
    response = await client.get(
        "/api/aois",
        params={"uiSchema": "reader-v1"},
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()[0]["uiSchema"] == "reader-v1"

    student_token = await login(client, student_email)
    denied = await client.get(
        "/api/aois",
        params={"uiSchema": "reader-v1"},
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert denied.status_code == 403
