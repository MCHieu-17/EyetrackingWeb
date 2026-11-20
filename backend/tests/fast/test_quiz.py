"""Quiz: ẩn đáp án, attempt, snapshot, chấm điểm, retry."""

from __future__ import annotations

import pytest

from tests.conftest import (
    create_course,
    create_quiz,
    create_user,
    execute,
    fetch_one,
    login,
)

pytestmark = pytest.mark.fast


async def _quiz_fixture(*, allow_retry=False, allow_chatbot=False, status="published"):
    teacher = await create_user(role="teacher", email=f"t-quiz-{allow_retry}@example.com")
    student = await create_user(email=f"s-quiz-{allow_retry}@example.com")
    ids = await create_course(
        teacher_id=teacher["id"],
        student_id=student["id"],
        status="published",
        require_calibration=False,
    )
    quiz_id = await create_quiz(
        module_id=ids["module_id"],
        allow_retry=allow_retry,
        allow_chatbot=allow_chatbot,
        status=status,
    )
    return teacher, student, ids, quiz_id


async def test_quiz_spec_hides_answers_for_student(client_factory):
    teacher, student, _ids, quiz_id = await _quiz_fixture()
    student_client = await client_factory()
    await login(student_client, student["email"])
    spec = await student_client.get(f"/api/lessons/{quiz_id}/quiz")
    assert spec.status_code == 200, spec.text
    question = spec.json()["questions"][0]
    assert question["correctOptionIds"] == []
    assert question["explanation"] == ""

    teacher_client = await client_factory()
    await login(teacher_client, teacher["email"])
    teacher_spec = await teacher_client.get(f"/api/lessons/{quiz_id}/quiz")
    assert teacher_spec.status_code == 200
    assert teacher_spec.json()["questions"][0]["correctOptionIds"] == ["a"]
    assert teacher_spec.json()["questions"][0]["explanation"] == "1 + 1 = 2"


async def test_quiz_attempt_submit_grading_and_review(client):
    teacher = await create_user(role="teacher", email="t-quiz-flow@example.com")
    student = await create_user(email="s-quiz-flow@example.com")
    ids = await create_course(
        teacher_id=teacher["id"],
        student_id=student["id"],
        status="published",
        require_calibration=False,
    )
    quiz_id = await create_quiz(
        module_id=ids["module_id"], allow_retry=True
    )
    await login(client, student["email"])

    started = await client.post(f"/api/lessons/{quiz_id}/attempts")
    assert started.status_code == 201, started.text
    attempt = started.json()
    assert attempt["assignmentId"] == quiz_id
    assert attempt["status"] == "in_progress"
    assert attempt["answers"] == {}
    assert attempt["score"] == 0

    resumed = await client.post(f"/api/lessons/{quiz_id}/attempts")
    assert resumed.status_code == 201
    assert resumed.json()["id"] == attempt["id"]

    submitted = await client.post(
        f"/api/attempts/{attempt['id']}/submit",
        json={"answers": {"q1": ["a"]}},
    )
    assert submitted.status_code == 200, submitted.text
    result = submitted.json()
    assert result["status"] == "submitted"
    assert result["score"] == 1
    assert result["maxScore"] == 1
    assert result["answers"] == {"q1": ["a"]}

    review = await client.get(f"/api/lessons/{quiz_id}/quiz")
    assert review.status_code == 200
    assert review.json()["questions"][0]["correctOptionIds"] == ["a"]

    second_submit = await client.post(
        f"/api/attempts/{attempt['id']}/submit",
        json={"answers": {"q1": ["a"]}},
    )
    assert second_submit.status_code == 409
    assert second_submit.json()["detail"]["code"] == "attempt_submitted"


async def test_quiz_incorrect_answer_scores_zero(client):
    teacher = await create_user(role="teacher", email="t-quiz-wrong@example.com")
    student = await create_user(email="s-quiz-wrong@example.com")
    ids = await create_course(
        teacher_id=teacher["id"], student_id=student["id"], status="published"
    )
    quiz_id = await create_quiz(module_id=ids["module_id"])
    await login(client, student["email"])
    attempt = (await client.post(f"/api/lessons/{quiz_id}/attempts")).json()
    result = await client.post(
        f"/api/attempts/{attempt['id']}/submit",
        json={"answers": {"q1": ["b"]}},
    )
    assert result.status_code == 200
    assert result.json()["score"] == 0
    assert result.json()["maxScore"] == 1


async def test_quiz_retry_permissions_and_new_attempt(client):
    teacher = await create_user(role="teacher", email="t-quiz-retry@example.com")
    student = await create_user(email="s-quiz-retry@example.com")
    ids = await create_course(
        teacher_id=teacher["id"], student_id=student["id"], status="published"
    )
    quiz_id = await create_quiz(module_id=ids["module_id"], allow_retry=False)
    await login(client, student["email"])
    attempt = (await client.post(f"/api/lessons/{quiz_id}/attempts")).json()
    await client.post(
        f"/api/attempts/{attempt['id']}/submit", json={"answers": {"q1": ["a"]}}
    )

    denied = await client.post(f"/api/attempts/{attempt['id']}/retry")
    assert denied.status_code == 403

    no_new = await client.post(f"/api/lessons/{quiz_id}/attempts")
    assert no_new.status_code == 409

    await execute(
        "UPDATE lessons SET quiz_config = jsonb_set(quiz_config, "
        "'{allowRetry}', 'true'::jsonb) WHERE id = :id",
        {"id": quiz_id},
    )
    allowed = await client.post(f"/api/attempts/{attempt['id']}/retry")
    assert allowed.status_code == 201, allowed.text
    assert allowed.json()["id"] != attempt["id"]
    assert allowed.json()["status"] == "in_progress"

    # Retry khi đang có attempt in_progress trả lại attempt đó.
    again = await client.post(f"/api/attempts/{attempt['id']}/retry")
    assert again.status_code == 201
    assert again.json()["id"] == allowed.json()["id"]


async def test_quiz_expired_attempt(client):
    teacher = await create_user(role="teacher", email="t-quiz-exp@example.com")
    student = await create_user(email="s-quiz-exp@example.com")
    ids = await create_course(
        teacher_id=teacher["id"], student_id=student["id"], status="published"
    )
    quiz_id = await create_quiz(module_id=ids["module_id"])
    await login(client, student["email"])
    attempt = (await client.post(f"/api/lessons/{quiz_id}/attempts")).json()
    await execute(
        "UPDATE quiz_attempts SET expires_at = now() - interval '1 second' "
        "WHERE id = :id",
        {"id": attempt["id"]},
    )
    response = await client.post(
        f"/api/attempts/{attempt['id']}/submit", json={"answers": {"q1": ["a"]}}
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "attempt_expired"
    row = await fetch_one(
        "SELECT status FROM quiz_attempts WHERE id = :id", {"id": attempt["id"]}
    )
    assert row["status"] == "expired"


async def test_quiz_snapshot_is_immutable(client):
    teacher = await create_user(role="teacher", email="t-quiz-snap@example.com")
    student = await create_user(email="s-quiz-snap@example.com")
    ids = await create_course(
        teacher_id=teacher["id"], student_id=student["id"], status="published"
    )
    quiz_id = await create_quiz(module_id=ids["module_id"])
    await login(client, student["email"])
    attempt = (await client.post(f"/api/lessons/{quiz_id}/attempts")).json()

    await execute(
        "UPDATE lessons SET quiz_config = jsonb_set(quiz_config, "
        "'{questions,0,correctOptionIds}', '[\"b\"]'::jsonb) WHERE id = :id",
        {"id": quiz_id},
    )
    result = await client.post(
        f"/api/attempts/{attempt['id']}/submit", json={"answers": {"q1": ["a"]}}
    )
    assert result.status_code == 200
    assert result.json()["score"] == 1


async def test_quiz_draft_course_cannot_start(client):
    teacher = await create_user(role="teacher", email="t-quiz-draft@example.com")
    student = await create_user(email="s-quiz-draft@example.com")
    ids = await create_course(
        teacher_id=teacher["id"],
        student_id=student["id"],
        status="draft",
        require_calibration=False,
    )
    quiz_id = await create_quiz(module_id=ids["module_id"])
    await login(client, student["email"])
    response = await client.post(f"/api/lessons/{quiz_id}/attempts")
    assert response.status_code == 404


async def test_quiz_attempt_list_permissions(client_factory):
    teacher = await create_user(role="teacher", email="t-quiz-list@example.com")
    student = await create_user(email="s-quiz-list@example.com")
    ids = await create_course(
        teacher_id=teacher["id"], student_id=student["id"], status="published"
    )
    quiz_id = await create_quiz(module_id=ids["module_id"])
    student_client = await client_factory()
    await login(student_client, student["email"])
    attempt = (await student_client.post(f"/api/lessons/{quiz_id}/attempts")).json()

    mine = await student_client.get(f"/api/lessons/{quiz_id}/attempts")
    assert mine.status_code == 200
    assert [item["id"] for item in mine.json()] == [attempt["id"]]

    other = await create_user(email="s-quiz-list-other@example.com")
    other_client = await client_factory()
    await login(other_client, other["email"])
    assert (
        await other_client.get(f"/api/lessons/{quiz_id}/attempts")
    ).status_code == 403

    teacher_client = await client_factory()
    await login(teacher_client, teacher["email"])
    all_attempts = await teacher_client.get(f"/api/lessons/{quiz_id}/attempts")
    assert all_attempts.status_code == 200
    assert len(all_attempts.json()) == 1
