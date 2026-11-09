import uuid

import pytest

from tests.conftest import create_user, login


@pytest.mark.asyncio
async def test_admin_list_and_promote_student(client):
    admin_email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    await create_user(email=admin_email, role="admin")
    student_id = await create_user(email=student_email)

    token = await login(client, admin_email)
    headers = {"Authorization": f"Bearer {token}"}

    students = await client.get(
        f"/admin/students?q={student_email}", headers=headers
    )
    assert students.status_code == 200, students.text
    assert any(item["id"] == student_id for item in students.json())

    promoted = await client.post(
        f"/admin/students/{student_id}/promote",
        headers=headers,
        json={"teacherCode": f"GV{uuid.uuid4().hex[:6].upper()}", "department": "Test"},
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["ok"] is True
