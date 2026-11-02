import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.chat import _sse, require_internal_token
from app.schemas import ChatRequest, HistoryMessage


def test_chat_request_valid():
    payload = ChatRequest(
        message="Khóa chính là gì?",
        course_id="course-1",
        thread_id="thread-1",
        history=[HistoryMessage(role="student", content="Xin chào")],
    )
    assert payload.message == "Khóa chính là gì?"
    assert payload.history[0].role == "student"


def test_chat_request_rejects_empty_message():
    with pytest.raises(ValidationError):
        ChatRequest(message="", course_id="course-1", thread_id="thread-1")


def test_history_role_validation():
    with pytest.raises(ValidationError):
        HistoryMessage(role="system", content="x")


def test_sse_format():
    frame = _sse("token", {"text": "Xin chào"})
    assert frame.startswith("event: token\n")
    assert 'data: {"text": "Xin chào"}' in frame
    assert frame.endswith("\n\n")


def test_internal_token_ok():
    require_internal_token("test-token")


def test_internal_token_rejected():
    with pytest.raises(HTTPException) as exc:
        require_internal_token("wrong")
    assert exc.value.status_code == 401
