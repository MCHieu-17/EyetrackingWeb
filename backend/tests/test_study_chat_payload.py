"""Contract: payload gửi chatbot giữ đúng assignment_id và attempt_id."""

from types import SimpleNamespace

from app.services import chat_payload

QUIZ = {
    "instructions": "Chọn đáp án đúng.",
    "questions": [
        {
            "id": "q1",
            "prompt": "1 + 1 bằng mấy?",
            "options": [
                {"id": "a", "text": "2"},
                {"id": "b", "text": "3"},
            ],
            "correctOptionIds": ["a"],
            "explanation": "1 + 1 = 2",
        }
    ],
}


def _payload(*, quiz=QUIZ, attempt=None, support_mode="hint", draft_answers=None):
    return chat_payload.payload(
        course=SimpleNamespace(id="course-1", title="Khóa học"),
        session=SimpleNamespace(id="session-1", context_key="ctx-1"),
        message="Gợi ý cho em",
        history_messages=[],
        lesson=SimpleNamespace(id="lesson-1", title="Bài tập 1"),
        module_title="Chương 1",
        quiz=quiz,
        attempt=attempt,
        support_mode=support_mode,
        draft_answers=draft_answers,
    )


def test_payload_omits_assignment_id_without_quiz_context():
    payload = _payload(quiz=None)

    assert payload["assignment_id"] is None
    assert payload["attempt_id"] is None
    assert payload["assignment_context"] == ""


def test_payload_forwards_quiz_assignment_and_in_progress_attempt():
    attempt = SimpleNamespace(id="attempt-1", status="in_progress", answers={"q1": ["b"]})

    payload = _payload(attempt=attempt, support_mode="hint")

    assert payload["assignment_id"] == "lesson-1"
    assert payload["lesson_id"] == "lesson-1"
    assert payload["attempt_id"] == "attempt-1"
    assert payload["support_mode"] == "hint"
    assert "Học viên chọn: b" in payload["assignment_context"]
    assert "Đáp án đúng" not in payload["assignment_context"]


def test_payload_submitted_attempt_review_includes_answers():
    attempt = SimpleNamespace(id="attempt-2", status="submitted", answers={"q1": ["b"]})

    hint = _payload(attempt=attempt, support_mode="hint")
    review = _payload(attempt=attempt, support_mode="review")

    assert hint["assignment_id"] == review["assignment_id"] == "lesson-1"
    assert hint["attempt_id"] == review["attempt_id"] == "attempt-2"
    assert "Đáp án đúng" not in hint["assignment_context"]
    assert "Đáp án đúng: a" in review["assignment_context"]
    assert "Giải thích: 1 + 1 = 2" in review["assignment_context"]
