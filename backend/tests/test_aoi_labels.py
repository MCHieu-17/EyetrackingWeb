"""Nhãn phân tích AOI: slide leaf dùng AOI_n, UI giữ tên hiển thị."""

import uuid

import pytest

from tests.conftest import create_user, login, seed_course, seed_slide


def _definition(code: str, *, name: str | None = None, label: str | None = None):
    return {
        "code": code,
        "name": name or code,
        "label": label,
        "geometry": {"xMin": 0.1, "yMin": 0.1, "xMax": 0.4, "yMax": 0.4},
        "isContainer": False,
        "kind": "custom",
        "isActive": True,
    }


@pytest.mark.asyncio
async def test_slide_save_assigns_aio_labels_and_preserves_them(client):
    email = f"aoi-label-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=email, role="teacher")
    student_id = await create_user(email=f"s-{uuid.uuid4().hex[:8]}@example.com")
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    slide = await seed_slide(
        course_id=ids["course_id"],
        lesson_id=ids["lesson_id"],
        teacher_id=teacher_id,
    )
    token = await login(client, email)
    headers = {"Authorization": f"Bearer {token}"}

    root = {
        "code": "slide_1",
        "name": "Slide 1",
        "label": None,
        "geometry": {"xMin": 0, "yMin": 0, "xMax": 1, "yMax": 1},
        "isContainer": True,
        "kind": "system",
        "isActive": True,
    }
    response = await client.put(
        f"/api/aois/slides/{slide['slide_id']}",
        json={"definitions": [root, _definition("a"), _definition("b")]},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    definitions = {
        item["code"]: item for item in response.json()["definitions"]
    }
    assert definitions["slide_1"]["label"] is None
    assert definitions["a"]["label"] == "AOI_1"
    assert definitions["b"]["label"] == "AOI_2"

    # Gửi lại đúng label cũ -> không đổi.
    response = await client.put(
        f"/api/aois/slides/{slide['slide_id']}",
        json={
            "definitions": [
                root,
                _definition("a", label="AOI_1"),
                _definition("b", label="AOI_2"),
            ]
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    definitions = {
        item["code"]: item for item in response.json()["definitions"]
    }
    assert definitions["a"]["label"] == "AOI_1"
    assert definitions["b"]["label"] == "AOI_2"

    # Xóa AOI_2 rồi thêm vùng mới -> cấp lại AOI_2.
    response = await client.put(
        f"/api/aois/slides/{slide['slide_id']}",
        json={
            "definitions": [
                root,
                _definition("a", label="AOI_1"),
                _definition("c"),
            ]
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    definitions = {
        item["code"]: item for item in response.json()["definitions"]
    }
    assert definitions["c"]["label"] == "AOI_2"


@pytest.mark.asyncio
async def test_slide_save_rejects_duplicate_label(client):
    email = f"aoi-dupe-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=email, role="teacher")
    student_id = await create_user(email=f"s-{uuid.uuid4().hex[:8]}@example.com")
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    slide = await seed_slide(
        course_id=ids["course_id"],
        lesson_id=ids["lesson_id"],
        teacher_id=teacher_id,
    )
    token = await login(client, email)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.put(
        f"/api/aois/slides/{slide['slide_id']}",
        json={
            "definitions": [
                _definition("a", label="AOI_1"),
                _definition("b", label="AOI_1"),
            ]
        },
        headers=headers,
    )
    assert response.status_code == 400
