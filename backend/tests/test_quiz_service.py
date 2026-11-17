"""Unit tests cho serialization/grading/scheduling quiz."""

from datetime import datetime, timezone

from app.services.quiz import attempt_expiry, grade_answers


def _config(due_at: str | None = None) -> dict:
    return {
        "durationMinutes": 30,
        "dueAt": due_at,
        "questions": [
            {"id": "q1", "points": 2, "correctOptionIds": ["a", "b"]},
            {"id": "q2", "points": 1, "correctOptionIds": ["c"]},
        ],
    }


def test_grading_is_all_or_nothing_and_rejects_empty_correct_set():
    grading, score, max_score = grade_answers(
        {
            "questions": [
                {"id": "q1", "points": 2, "correctOptionIds": ["a", "b"]},
                {"id": "q2", "points": 1, "correctOptionIds": []},
            ]
        },
        {"q1": ["a"], "q2": []},
    )
    assert score == 0
    assert max_score == 3
    assert grading["q1"] == {"correct": False, "points": 0}
    assert grading["q2"] == {"correct": False, "points": 0}


def test_grading_scores_complete_match():
    _, score, max_score = grade_answers(
        _config(), {"q1": ["b", "a"], "q2": ["c"]}
    )
    assert score == 3
    assert max_score == 3


def test_attempt_expiry_uses_min_of_duration_and_due_date():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert attempt_expiry(_config(), now).hour == 12
    assert attempt_expiry(_config(), now).minute == 30
    capped = attempt_expiry(_config("2026-01-01T12:10:00+00:00"), now)
    assert capped.hour == 12
    assert capped.minute == 10


def test_attempt_expiry_treats_naive_due_date_as_utc():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    capped = attempt_expiry(_config("2026-01-01T12:10:00"), now)
    assert capped == datetime(2026, 1, 1, 12, 10, tzinfo=timezone.utc)
