"""Tests cho chuẩn hoá lịch sử hội thoại."""

from langchain_core.messages import AIMessage, HumanMessage

from app.workflow.history import _history_messages, budget_history


def test_history_messages_maps_roles_and_filters_empty_content():
    history = [
        {"role": "student", "content": "  Câu hỏi 1  "},
        {"role": "assistant", "content": "Trả lời 1"},
        {"role": "student", "content": "   "},
        {"role": "assistant", "content": ""},
        {"role": "student", "content": "Câu hỏi 2"},
    ]

    messages = _history_messages(history)

    assert [isinstance(message, HumanMessage) for message in messages] == [True, False, True]
    assert [isinstance(message, AIMessage) for message in messages] == [False, True, False]
    assert [message.content for message in messages] == [
        "Câu hỏi 1",
        "Trả lời 1",
        "Câu hỏi 2",
    ]


def test_budget_history_keeps_recent_items_within_budget():
    history = [
        {"role": "student", "content": "a" * 10},
        {"role": "assistant", "content": "b" * 10},
    ]

    assert budget_history(history, max_chars=15) == [history[1]]
    assert budget_history(history, max_chars=20) == history
    assert budget_history([], max_chars=10) == []
