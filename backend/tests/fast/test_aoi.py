"""AOI slide/UI: validate, replace, label, phân quyền, enqueue phân tích."""

from __future__ import annotations

import pytest

from tests.conftest import (
    create_course,
    create_lesson,
    create_slide,
    create_user,
    fetch_all,
    fetch_one,
    login,
)

pytestmark = pytest.mark.fast


async def _fixture():
    teacher = await create_user(role="teacher", email="t-aoi@example.com")
    ids = await create_course(teacher_id=teacher["id"])
    lesson_id = await create_lesson(module_id=ids["module_id"])
    slide_id = await create_slide(lesson_id=lesson_id)
    return teacher, ids, lesson_id, slide_id


def _definition(code: str, **overrides):
    data = {
        "code": code,
        "name": f"Vùng {code}",
        "label": None,
        "geometry": {"xMin": 0.1, "yMin": 0.1, "xMax": 0.5, "yMax": 0.5},
        "isContainer": False,
        "kind": "custom",
        "isActive": True,
    }
    data.update(overrides)
    return data


async def test_save_slide_aois_replaces_and_assigns_labels(client):
    teacher, _ids, lesson_id, slide_id = await _fixture()
    await login(client, teacher["email"])
    response = await client.put(
        f"/api/aois/slides/{slide_id}",
        json={
            "definitions": [
                _definition("vung_1", label="AOI_1"),
                _definition("vung_2", label="aoi_2"),
                _definition("vung_3"),
            ]
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["scope"] == "slide"
    assert body["slideId"] == slide_id
    by_code = {item["code"]: item for item in body["definitions"]}
    assert set(by_code) == {"vung_1", "vung_2", "vung_3", "no_label"}
    assert [item["code"] for item in body["definitions"]] == sorted(by_code)
    assert by_code["vung_1"]["label"] == "AOI_1"
    assert by_code["vung_2"]["label"] == "AOI_2"
    assert by_code["vung_3"]["label"] == "AOI_3"
    assert by_code["no_label"]["kind"] == "system"

    jobs = await fetch_all(
        "SELECT kind, status FROM background_jobs WHERE lesson_id = :id",
        {"id": lesson_id},
    )
    assert any(job["kind"] == "analyze_lesson" for job in jobs)


async def test_save_slide_rejects_invalid_label_geometry_and_duplicates(client):
    teacher, _ids, _lesson_id, slide_id = await _fixture()
    await login(client, teacher["email"])
    url = f"/api/aois/slides/{slide_id}"

    invalid_label = await client.put(
        url,
        json={"definitions": [_definition("a", label="SAI")]},
    )
    assert invalid_label.status_code == 400

    invalid_geometry = await client.put(
        url,
        json={
            "definitions": [
                _definition(
                    "a",
                    geometry={"xMin": 0.9, "yMin": 0.1, "xMax": 0.1, "yMax": 0.5},
                )
            ]
        },
    )
    assert invalid_geometry.status_code == 400

    duplicate = await client.put(
        url,
        json={"definitions": [_definition("a"), _definition("a")]},
    )
    assert duplicate.status_code == 400


async def test_slide_label_is_preserved_by_code(client):
    teacher, _ids, _lesson_id, slide_id = await _fixture()
    await login(client, teacher["email"])
    url = f"/api/aois/slides/{slide_id}"
    first = await client.put(
        url, json={"definitions": [_definition("a", label="AOI_CUSTOM")]}
    )
    assert first.status_code == 200
    second = await client.put(url, json={"definitions": [_definition("a")]})
    assert second.status_code == 200
    labels = {item["code"]: item["label"] for item in second.json()["definitions"]}
    assert labels["a"] == "AOI_CUSTOM"


async def test_ui_aoi_generate_and_save(client):
    teacher = await create_user(role="teacher", email="t-aoi-ui@example.com")
    await login(client, teacher["email"])
    generated = await client.post(
        "/api/aois/ui/reader-v1/generate",
        json={
            "components": [
                {"code": "header", "name": "Header"},
                {"code": "lesson-content", "name": "Nội dung bài"},
            ],
            "merge": True,
        },
    )
    assert generated.status_code == 200, generated.text
    body = generated.json()
    by_code = {item["code"]: item for item in body["definitions"]}
    assert by_code["header"]["geometry"]["selector"] == "[data-aoi='header']"
    assert by_code["lesson-content"]["kind"] == "ui"

    repeated = await client.post(
        "/api/aois/ui/reader-v1/generate",
        json={
            "components": [{"code": "header", "name": "Header"}],
            "merge": True,
        },
    )
    assert repeated.status_code == 200
    assert len(repeated.json()["definitions"]) == len(body["definitions"])

    duplicate_name = await client.put(
        "/api/aois/ui/reader-v1",
        json={
            "definitions": [
                {
                    "code": "a",
                    "name": "Trùng",
                    "geometry": {"selector": "[data-aoi='a']"},
                    "kind": "ui",
                },
                {
                    "code": "b",
                    "name": "trùng",
                    "geometry": {"selector": "[data-aoi='b']"},
                    "kind": "ui",
                },
            ]
        },
    )
    assert duplicate_name.status_code == 400

    reserved = await client.put(
        "/api/aois/ui/reader-v1",
        json={
            "definitions": [
                {
                    "code": "a",
                    "name": "SLIDE_X",
                    "geometry": {"selector": "[data-aoi='a']"},
                    "kind": "ui",
                }
            ]
        },
    )
    assert reserved.status_code == 400


async def test_aoi_permissions(client_factory):
    _teacher, _ids, _lesson_id, slide_id = await _fixture()
    student = await create_user(email="aoi-student@example.com")
    other_teacher = await create_user(role="teacher", email="aoi-other@example.com")

    student_client = await client_factory()
    await login(student_client, student["email"])
    assert (
        await student_client.put(
            f"/api/aois/slides/{slide_id}",
            json={"definitions": [_definition("a")]},
        )
    ).status_code == 403
    assert (await student_client.get("/api/aois?slideId=" + slide_id)).status_code == 403

    other_client = await client_factory()
    await login(other_client, other_teacher["email"])
    assert (
        await other_client.put(
            f"/api/aois/slides/{slide_id}",
            json={"definitions": [_definition("a")]},
        )
    ).status_code == 403


async def test_aoi_rebuild_returns_lesson_count(client):
    teacher, ids, lesson_id, _slide_id = await _fixture()
    await login(client, teacher["email"])
    response = await client.post(
        "/api/aoi/rebuild", json={"courseId": ids["course_id"]}
    )
    assert response.status_code == 200, response.text
    assert response.json()["runs"] == 1
    assert response.json()["completed"] == 0
    assert response.json()["failed"] == 0
    job = await fetch_one(
        "SELECT status FROM background_jobs WHERE lesson_id = :id "
        "AND kind = 'analyze_lesson'",
        {"id": lesson_id},
    )
    assert job["status"] == "queued"
