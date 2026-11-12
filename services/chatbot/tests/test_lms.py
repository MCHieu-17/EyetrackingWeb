"""Tests cho LMS detection và render."""

from app.workflow.lms import detect_operation, is_pure_lms, render


def test_detect_operation():
    assert detect_operation("Hạn nộp bài tập 1 là khi nào?") == "assignments"
    assert detect_operation("Điểm của tôi") == "results"
    assert detect_operation("Cấu trúc khóa học") == "structure"
    assert detect_operation("Thông tin khóa học") == "course"
    assert detect_operation("Giải thích khái niệm X") is None


def test_is_pure_lms():
    assert is_pure_lms("Hạn nộp bài tập 1 là khi nào?") is True
    assert is_pure_lms("Điểm của tôi") is True
    assert is_pure_lms("Giải thích bài tập 1") is False
    assert is_pure_lms("Bài tập này có mấy câu?") is False
    assert is_pure_lms("Giải thích khái niệm X") is False


def test_render_assignments():
    data = {
        "assignments": [
            {
                "title": "Bài 1",
                "url": "/student/courses/c1?lesson=l1",
                "status": "đang làm",
                "duration_minutes": 30,
                "due_at": None,
                "attempt_deadline": None,
                "remaining_seconds": 60,
                "score": None,
                "max_score": None,
            }
        ]
    }

    text = render(data, "assignments")

    assert "Bài 1" in text
    assert "đang làm" in text
    assert "1 phút 0 giây" in text


def test_render_results_includes_score():
    data = {
        "assignments": [
            {
                "title": "Bài 1",
                "url": "/x",
                "status": "đã nộp",
                "duration_minutes": 30,
                "due_at": None,
                "attempt_deadline": None,
                "remaining_seconds": None,
                "score": 8,
                "max_score": 10,
            }
        ]
    }

    text = render(data, "results")

    assert "8/10" in text


def test_render_clarification():
    data = {
        "clarification": "Hãy chọn đúng bài tập.",
        "choices": [{"id": "a1", "title": "Bài 1"}],
    }

    text = render(data, "assignments")

    assert "Hãy chọn đúng bài tập." in text
    assert "Bài 1" in text
