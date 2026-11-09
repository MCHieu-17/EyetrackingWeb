import uuid

import pytest

from tests.conftest import create_user, login, seed_course


@pytest.mark.asyncio
async def test_chat_access_and_sessions(client):
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)

    token = await login(client, student_email)
    headers = {"Authorization": f"Bearer {token}"}

    access = await client.get(
        f"/api/courses/{ids['course_id']}/chat/access", headers=headers
    )
    assert access.status_code == 200, access.text
    assert access.json()["allowed"] is True

    sessions = await client.get(
        f"/api/courses/{ids['course_id']}/chat/sessions", headers=headers
    )
    assert sessions.status_code == 200, sessions.text
    assert sessions.json() == []


@pytest.mark.asyncio
async def test_chat_stream_rate_limited_per_account(client):
    """Mỗi tài khoản chỉ gửi được 1 tin nhắn chatbot trong 5 giây."""
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    student_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=teacher_email, role="teacher")
    student_id = await create_user(email=student_email)
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)

    token = await login(client, student_email)
    headers = {"Authorization": f"Bearer {token}"}
    body = {"message": "Xin chào", "lessonId": ids["lesson_id"]}
    url = f"/api/courses/{ids['course_id']}/chat/stream"

    first = await client.post(url, json=body, headers=headers)
    assert first.status_code == 200, first.text

    second = await client.post(url, json=body, headers=headers)
    assert second.status_code == 429, second.text
    assert int(second.headers["Retry-After"]) >= 1
    assert second.json()["detail"] == "Bạn gửi tin nhắn quá nhanh."

    # Tài khoản khác không bị ảnh hưởng bởi giới hạn của tài khoản thứ nhất.
    other_email = f"student-{uuid.uuid4().hex[:8]}@example.com"
    other_id = await create_user(email=other_email)
    other_ids = await seed_course(teacher_id=teacher_id, student_id=other_id)
    other_token = await login(client, other_email)
    other = await client.post(
        f"/api/courses/{other_ids['course_id']}/chat/stream",
        json={"message": "Xin chào", "lessonId": other_ids["lesson_id"]},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert other.status_code == 200, other.text
