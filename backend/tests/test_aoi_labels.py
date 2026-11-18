"""Nhãn phân tích AOI: slide leaf dùng AOI_..., UI giữ tên hiển thị."""

import uuid

import pytest

from app.core.config import settings
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


def _root() -> dict:
    return {
        "code": "slide_1",
        "name": "Slide 1",
        "label": None,
        "geometry": {"xMin": 0, "yMin": 0, "xMax": 1, "yMax": 1},
        "isContainer": True,
        "kind": "system",
        "isActive": True,
    }


async def _seed_teacher_slide(client, prefix: str):
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=email, role="teacher")
    student_id = await create_user(email=f"s-{uuid.uuid4().hex[:8]}@example.com")
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    slide = await seed_slide(
        course_id=ids["course_id"],
        lesson_id=ids["lesson_id"],
        teacher_id=teacher_id,
    )
    token = await login(client, email)
    return slide, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_slide_save_assigns_and_preserves_aio_labels(client):
    slide, headers = await _seed_teacher_slide(client, "aoi-label")

    # Chưa có nhãn -> tự cấp AOI_n; nhãn giáo viên được uppercase và giữ nguyên.
    response = await client.put(
        f"/api/aois/slides/{slide['slide_id']}",
        json={
            "definitions": [
                _root(),
                _definition("a"),
                _definition("b"),
                _definition("c", label="aoi_thanhchat"),
            ]
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    definitions = {
        item["code"]: item for item in response.json()["definitions"]
    }
    assert definitions["slide_1"]["label"] is None
    assert definitions["a"]["label"] == "AOI_1"
    assert definitions["b"]["label"] == "AOI_2"
    assert definitions["c"]["label"] == "AOI_THANHCHAT"

    # Gửi lại không kèm label -> giữ nhãn cũ, kể cả nhãn giáo viên.
    response = await client.put(
        f"/api/aois/slides/{slide['slide_id']}",
        json={
            "definitions": [
                _root(),
                _definition("a"),
                _definition("b"),
                _definition("c"),
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
    assert definitions["c"]["label"] == "AOI_THANHCHAT"

    # Xóa AOI_2 rồi thêm vùng mới -> cấp lại AOI_2, không đụng nhãn custom.
    response = await client.put(
        f"/api/aois/slides/{slide['slide_id']}",
        json={
            "definitions": [
                _root(),
                _definition("a"),
                _definition("c"),
                _definition("d"),
            ]
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    definitions = {
        item["code"]: item for item in response.json()["definitions"]
    }
    assert definitions["a"]["label"] == "AOI_1"
    assert definitions["c"]["label"] == "AOI_THANHCHAT"
    assert definitions["d"]["label"] == "AOI_2"


@pytest.mark.asyncio
async def test_slide_save_rejects_duplicate_label(client):
    slide, headers = await _seed_teacher_slide(client, "aoi-dupe")

    for label in ("AOI_1", "AOI_THANHCHAT"):
        response = await client.put(
            f"/api/aois/slides/{slide['slide_id']}",
            json={
                "definitions": [
                    _definition("a", label=label),
                    _definition("b", label=label),
                ]
            },
            headers=headers,
        )
        assert response.status_code == 400, response.text


@pytest.mark.asyncio
async def test_slide_save_rejects_invalid_label(client):
    slide, headers = await _seed_teacher_slide(client, "aoi-invalid")

    for label in ("SLIDE_AOI_1", "THANHCHAT", "AOI_BANG BIEU", "AOI_"):
        response = await client.put(
            f"/api/aois/slides/{slide['slide_id']}",
            json={"definitions": [_definition("a", label=label)]},
            headers=headers,
        )
        assert response.status_code == 400, response.text


@pytest.mark.asyncio
async def test_slide_save_accepts_cookie_auth_from_same_origin(client, monkeypatch):
    """Regression: hostname mới không có trong CORS_ORIGINS vẫn phải lưu được."""
    email = f"aoi-cookie-{uuid.uuid4().hex[:8]}@example.com"
    teacher_id = await create_user(email=email, role="teacher")
    student_id = await create_user(email=f"s-{uuid.uuid4().hex[:8]}@example.com")
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    slide = await seed_slide(
        course_id=ids["course_id"],
        lesson_id=ids["lesson_id"],
        teacher_id=teacher_id,
    )
    # Login bằng cookie, không dùng Bearer để buộc middleware kiểm tra CSRF.
    await login(client, email)
    monkeypatch.setattr(settings, "cors_origins", "https://different.example")
    csrf = client.cookies.get("csrf_token")
    assert csrf
    headers = {"Origin": "http://testserver", "X-CSRF-Token": csrf}

    response = await client.put(
        f"/api/aois/slides/{slide['slide_id']}",
        json={"definitions": [_root(), _definition("a")]},
        headers=headers,
    )
    assert response.status_code == 200, response.text

    # Cross-origin lạ vẫn bị chặn dù token đúng.
    response = await client.put(
        f"/api/aois/slides/{slide['slide_id']}",
        json={"definitions": [_root(), _definition("a")]},
        headers={"Origin": "https://evil.example", "X-CSRF-Token": csrf},
    )
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "Origin không hợp lệ"
