"""Phase 3 smoke: quiz spec → attempt → submit → retry."""

from __future__ import annotations

import asyncio

import pytest

from tests.conftest import auth, login, make_user


@pytest.fixture()
def teacher(client):
    asyncio.run(make_user("teacher3@example.com", "teacher", full_name="GV Phase 3"))
    return login(client, "teacher3@example.com")


@pytest.fixture()
def student(client):
    asyncio.run(make_user("student3@example.com", "student", full_name="SV Phase 3"))
    return login(client, "student3@example.com")


def _create_published_quiz(client, teacher):
    headers = auth(teacher)
    course = client.post(
        "/teacher/courses", json={"title": "Khóa Quiz"}, headers=headers
    ).json()
    module = client.post(
        f"/teacher/courses/{course['id']}/modules",
        json={"title": "Chương"},
        headers=headers,
    ).json()
    quiz = client.post(
        f"/teacher/modules/{module['id']}/quizzes",
        json={"title": "Bài tập", "durationMinutes": 15},
        headers=headers,
    ).json()
    quiz_id = quiz["quizId"]
    lesson_id = quiz["id"]
    patched = client.patch(
        f"/api/teacher/quiz-specs/{quiz_id}",
        json={
            "allowRetry": True,
            "questions": [
                {
                    "id": "q1",
                    "prompt": "2 + 2 = ?",
                    "options": [
                        {"id": "a", "text": "4"},
                        {"id": "b", "text": "5"},
                    ],
                    "correctOptionIds": ["a"],
                    "allowMultiple": False,
                    "explanation": "4",
                    "points": 2,
                }
            ],
        },
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    published = client.post(
        f"/teacher/courses/{course['id']}/publish", json={}, headers=headers
    )
    assert published.status_code == 200, published.text
    return course["id"], lesson_id, quiz_id


def test_quiz_attempt_submit_and_retry(client, teacher, student):
    course_id, lesson_id, quiz_id = _create_published_quiz(client, teacher)
    student_headers = auth(student)

    enroll = client.post(f"/api/courses/{course_id}/enroll", headers=student_headers)
    assert enroll.status_code == 201, enroll.text

    spec = client.get(f"/api/quiz-specs/{quiz_id}", headers=student_headers)
    assert spec.status_code == 200, spec.text
    assert spec.json()["questions"][0]["correctOptionIds"] == []

    started = client.post(
        f"/api/lessons/{lesson_id}/attempts", headers=student_headers
    )
    assert started.status_code == 201, started.text
    attempt_id = started.json()["id"]
    assert started.json()["assignmentId"] == quiz_id

    submitted = client.post(
        f"/api/attempts/{attempt_id}/submit",
        json={"answers": {"q1": ["a"]}},
        headers=student_headers,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["score"] == 2
    assert submitted.json()["maxScore"] == 2

    revealed = client.get(f"/api/quiz-specs/{quiz_id}", headers=student_headers)
    assert revealed.status_code == 200, revealed.text
    assert revealed.json()["questions"][0]["correctOptionIds"] == ["a"]

    double = client.post(
        f"/api/attempts/{attempt_id}/submit",
        json={"answers": {"q1": ["a"]}},
        headers=student_headers,
    )
    assert double.status_code == 409

    retried = client.post(
        f"/api/attempts/{attempt_id}/retry", headers=student_headers
    )
    assert retried.status_code == 201, retried.text
    assert retried.json()["id"] != attempt_id

    history = client.get(
        f"/api/lessons/{lesson_id}/attempts", headers=student_headers
    )
    assert history.status_code == 200, history.text
    assert len(history.json()) == 2
