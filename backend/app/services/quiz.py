"""Serialization/scheduling/grading thuần cho quiz.

Route giữ phần HTTP, authorization và persistence; module này xử lý snapshot
đề, ẩn/hiện đáp án, tính điểm và thời điểm hết hạn.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.models.auth import User
from app.models.course import Course, Lesson
from app.models.quiz import QuizAttempt
from app.schemas.quiz import QuizAssignmentOut, QuizAttemptOut


def parse_datetime(value) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def public_question(question: dict) -> dict:
    clean = {key: value for key, value in question.items() if key != "correctOptionId"}
    clean["correctOptionIds"] = []
    clean["explanation"] = ""
    return clean


def reveal_question(question: dict) -> dict:
    clean = {key: value for key, value in question.items() if key != "correctOptionId"}
    clean["correctOptionIds"] = [
        str(item) for item in (question.get("correctOptionIds") or [])
    ]
    return clean


def attempt_out(attempt: QuizAttempt) -> QuizAttemptOut:
    return QuizAttemptOut(
        id=attempt.id,
        assignment_id=attempt.lesson_id,
        status=attempt.status,
        answers=attempt.answers,
        submitted_at=attempt.submitted_at or attempt.started_at,
        score=int(attempt.score or 0),
        max_score=int(attempt.max_score or 0),
    )


def assignment_out(
    *,
    course: Course,
    lesson: Lesson,
    config: dict,
    user: User,
    attempt: QuizAttempt | None,
) -> QuizAssignmentOut:
    reveal = user.role in {"teacher", "admin"} or (
        attempt is not None and attempt.status == "submitted"
    )
    source_config = (
        attempt.quiz_snapshot
        if attempt is not None and attempt.status == "submitted" and attempt.quiz_snapshot
        else config
    )
    questions = [
        reveal_question(question) if reveal else public_question(question)
        for question in (source_config.get("questions") or [])
    ]
    return QuizAssignmentOut(
        id=lesson.id,
        course_id=course.id,
        course_title=course.title,
        lesson_id=lesson.id,
        lesson_title=lesson.title,
        title=lesson.title,
        instructions=str(source_config.get("instructions") or ""),
        due_at=parse_datetime(source_config.get("dueAt")),
        duration_minutes=int(source_config.get("durationMinutes") or 15),
        status=str(source_config.get("status") or "draft"),
        created_at=lesson.created_at,
        expires_at=(
            attempt.expires_at
            if attempt and attempt.status == "in_progress"
            else None
        ),
        allow_chatbot=bool(source_config.get("allowChatbot")),
        allow_retry=bool(source_config.get("allowRetry")),
        questions=questions,
    )


def attempt_expiry(config: dict, now: datetime) -> datetime:
    expires_at = now + timedelta(minutes=int(config.get("durationMinutes") or 15))
    due_at = parse_datetime(config.get("dueAt"))
    if due_at is not None:
        expires_at = min(expires_at, due_at)
    return expires_at


def grade_answers(
    config: dict, answers: dict[str, list[str]]
) -> tuple[dict[str, dict], float, float]:
    grading: dict[str, dict] = {}
    score = 0.0
    max_score = 0.0
    for question in config.get("questions") or []:
        qid = str(question.get("id"))
        points = float(question.get("points") or 0)
        max_score += points
        selected = {str(item) for item in (answers.get(qid) or [])}
        correct = {str(item) for item in (question.get("correctOptionIds") or [])}
        is_correct = selected == correct and bool(correct)
        if is_correct:
            score += points
        grading[qid] = {"correct": is_correct, "points": points if is_correct else 0}
    return grading, score, max_score
