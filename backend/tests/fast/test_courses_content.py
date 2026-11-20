"""Khóa hợp đồng course/module/lesson/student và phân quyền quản lý."""

from __future__ import annotations

import pytest

from tests.conftest import (
    create_course,
    create_lesson,
    create_slide,
    create_user,
    execute,
    fetch_all,
    fetch_one,
    login,
)

pytestmark = pytest.mark.fast


async def test_create_course_contract(client):
    teacher = await create_user(role="teacher", email="t-create@example.com")
    await login(client, teacher["email"])
    response = await client.post(
        "/teacher/courses",
        json={"title": "Khóa mới", "description": "Mô tả", "requireCalibration": False},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["title"] == "Khóa mới"
    assert body["status"] == "draft"
    assert body["isOwner"] is True
    assert body["showGazeDot"] is False
    assert body["requireCalibration"] is False
    assert body["lessonCount"] == 0
    assert body["students"] == 0


async def test_course_permissions_for_other_and_assigned_teacher(client_factory):
    owner = await create_user(role="teacher", email="owner@example.com")
    other = await create_user(role="teacher", email="other@example.com")
    assigned = await create_user(role="teacher", email="assigned@example.com")
    student = await create_user(email="student-course@example.com")
    ids = await create_course(
        teacher_id=owner["id"], student_id=student["id"], title="Private"
    )
    await execute(
        "INSERT INTO course_teachers (course_id, teacher_id) VALUES (:c, :t)",
        {"c": ids["course_id"], "t": assigned["id"]},
    )

    other_client = await client_factory()
    await login(other_client, other["email"])
    assert (
        await other_client.get(f"/teacher/courses/{ids['course_id']}")
    ).status_code == 403
    assert (
        await other_client.patch(
            f"/teacher/courses/{ids['course_id']}", json={"title": "Hack"}
        )
    ).status_code == 403

    assigned_client = await client_factory()
    await login(assigned_client, assigned["email"])
    tree = await assigned_client.get(f"/teacher/courses/{ids['course_id']}")
    assert tree.status_code == 200
    assert (
        await assigned_client.patch(
            f"/teacher/courses/{ids['course_id']}", json={"title": "Hack"}
        )
    ).status_code == 403
    assert (
        await assigned_client.post(
            f"/teacher/courses/{ids['course_id']}/publish"
        )
    ).status_code == 403

    student_client = await client_factory()
    await login(student_client, student["email"])
    assert (await student_client.get(f"/teacher/courses/{ids['course_id']}")).status_code == 403


async def test_admin_can_manage_any_course(client):
    owner = await create_user(role="teacher", email="owner2@example.com")
    admin = await create_user(role="admin", email="admin-course@example.com")
    ids = await create_course(teacher_id=owner["id"])
    await login(client, admin["email"])
    response = await client.patch(
        f"/teacher/courses/{ids['course_id']}", json={"title": "Admin sửa"}
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Admin sửa"


async def test_update_course_and_flags(client, client_factory):
    teacher = await create_user(role="teacher", email="t-update@example.com")
    student = await create_user(email="s-update@example.com")
    ids = await create_course(teacher_id=teacher["id"], student_id=student["id"])

    teacher_client = await client_factory()
    await login(teacher_client, teacher["email"])
    updated = await teacher_client.patch(
        f"/teacher/courses/{ids['course_id']}",
        json={"title": "Đổi tên", "description": "Mô tả mới", "status": "draft"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Đổi tên"

    invalid = await teacher_client.patch(
        f"/teacher/courses/{ids['course_id']}", json={"status": "invalid"}
    )
    assert invalid.status_code == 422

    dot = await teacher_client.patch(
        f"/teacher/courses/{ids['course_id']}/gaze-dot",
        json={"showGazeDot": True},
    )
    assert dot.status_code == 200
    assert dot.json() == {"ok": True, "showGazeDot": True}

    calibration = await teacher_client.patch(
        f"/teacher/courses/{ids['course_id']}/require-calibration",
        json={"requireCalibration": False},
    )
    assert calibration.status_code == 200
    assert calibration.json() == {"ok": True, "requireCalibration": False}

    # Học viên đã enroll thấy cache bị xoá qua API enrollments.
    student_client = await client_factory()
    await login(student_client, student["email"])
    enrollments = await student_client.get("/api/me/enrollments")
    assert enrollments.status_code == 200


async def test_module_lesson_and_reorder(client):
    teacher = await create_user(role="teacher", email="t-content@example.com")
    ids = await create_course(teacher_id=teacher["id"])
    await login(client, teacher["email"])

    module = await client.post(
        f"/teacher/courses/{ids['course_id']}/modules",
        json={"title": "Chương A"},
    )
    assert module.status_code == 201, module.text
    module_id = module.json()["id"]
    assert module.json()["orderIndex"] == 1

    lesson_one = await client.post(
        f"/teacher/modules/{module_id}/lessons", json={"title": "Bài A"}
    )
    assert lesson_one.status_code == 201
    lesson_two = await client.post(
        f"/teacher/modules/{module_id}/lessons", json={"title": "Bài B"}
    )
    assert lesson_two.status_code == 201

    quiz = await client.post(
        f"/teacher/modules/{module_id}/quizzes",
        json={"title": "Quiz A", "afterId": lesson_one.json()["id"]},
    )
    assert quiz.status_code == 201, quiz.text
    assert quiz.json()["kind"] == "quiz"
    assert quiz.json()["quizStatus"] == "draft"

    tree = await client.get(f"/teacher/courses/{ids['course_id']}")
    assert tree.status_code == 200
    node = next(item for item in tree.json() if item["id"] == module_id)
    lessons = node["lessons"]
    assert [item["title"] for item in lessons] == ["Bài A", "Quiz A", "Bài B"]

    reorder = await client.post(
        f"/teacher/modules/{module_id}/items/reorder",
        json={
            "items": [
                {"kind": "lesson", "id": lesson_two.json()["id"]},
                {"kind": "quiz", "id": quiz.json()["id"]},
                {"kind": "lesson", "id": lesson_one.json()["id"]},
            ]
        },
    )
    assert reorder.status_code == 200, reorder.text
    tree = await client.get(f"/teacher/courses/{ids['course_id']}")
    node = next(item for item in tree.json() if item["id"] == module_id)
    assert [item["title"] for item in node["lessons"]] == [
        "Bài B",
        "Quiz A",
        "Bài A",
    ]

    missing = await client.post(
        f"/teacher/modules/{module_id}/items/reorder",
        json={"items": [{"kind": "lesson", "id": lesson_one.json()["id"]}]},
    )
    assert missing.status_code == 400


async def test_students_add_and_remove(client):
    teacher = await create_user(role="teacher", email="t-students@example.com")
    student = await create_user(email="s-students@example.com")
    student_two = await create_user(email="s-students-2@example.com")
    ids = await create_course(teacher_id=teacher["id"])
    await login(client, teacher["email"])

    directory = await client.get("/teacher/students?q=SV")
    assert directory.status_code == 200

    added = await client.post(
        f"/teacher/courses/{ids['course_id']}/students",
        json={
            "studentIds": [student["id"], student["id"], student_two["id"]]
        },
    )
    assert added.status_code == 201, added.text
    assert added.json()["added"] == 2
    enrollment = await fetch_one(
        "SELECT id, status FROM enrollments WHERE course_id = :c AND student_id = :s",
        {"c": ids["course_id"], "s": student["id"]},
    )
    assert enrollment["status"] == "active"

    removed = await client.delete(
        f"/teacher/courses/{ids['course_id']}/students/{student['id']}"
    )
    assert removed.status_code == 200
    assert (
        await fetch_one(
            "SELECT status FROM enrollments WHERE id = :id",
            {"id": enrollment["id"]},
        )
    )["status"] == "dropped"

    again = await client.delete(
        f"/teacher/courses/{ids['course_id']}/students/{student['id']}"
    )
    assert again.status_code == 200


async def test_course_delete_cascades_content(client):
    teacher = await create_user(role="teacher", email="t-delete@example.com")
    ids = await create_course(teacher_id=teacher["id"])
    lesson_id = await create_lesson(module_id=ids["module_id"])
    await create_slide(lesson_id=lesson_id)
    await login(client, teacher["email"])

    response = await client.delete(f"/teacher/courses/{ids['course_id']}")
    assert response.status_code == 200
    assert await fetch_one(
        "SELECT id FROM courses WHERE id = :id", {"id": ids["course_id"]}
    ) is None
    assert await fetch_one(
        "SELECT id FROM lessons WHERE id = :id", {"id": lesson_id}
    ) is None
    assert await fetch_all(
        "SELECT id FROM slides WHERE lesson_id = :id", {"id": lesson_id}
    ) == []


async def test_outline_visibility_and_enrollment_cache(client_factory):
    teacher = await create_user(role="teacher", email="t-outline@example.com")
    student = await create_user(email="s-outline@example.com")
    ids = await create_course(
        teacher_id=teacher["id"], student_id=student["id"], status="published"
    )

    anonymous_enrolled = await client_factory()
    await login(anonymous_enrolled, student["email"])
    outline = await anonymous_enrolled.get(f"/api/courses/{ids['course_id']}")
    assert outline.status_code == 200
    assert outline.json()["title"] == "Test Course"
    assert outline.json()["requireCalibration"] is False

    other_student = await create_user(email="s-other@example.com")
    other_client = await client_factory()
    await login(other_client, other_student["email"])
    assert (await other_client.get(f"/api/courses/{ids['course_id']}")).status_code == 200

    draft_ids = await create_course(teacher_id=teacher["id"], status="draft")
    assert (
        await other_client.get(f"/api/courses/{draft_ids['course_id']}")
    ).status_code == 403
