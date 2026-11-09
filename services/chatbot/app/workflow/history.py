"""Chuẩn hoá lịch sử hội thoại thành message cho prompt."""

from langchain_core.messages import AIMessage, HumanMessage


def budget_history(history: list[dict], max_chars: int = 16000) -> list[dict]:
    selected = []
    remaining = max_chars
    for item in reversed(history[-10:]):
        text = item.get("content") or ""
        if len(text) > remaining:
            break
        selected.append(item)
        remaining -= len(text)
    return list(reversed(selected))


def _history_messages(history: list[dict]) -> list:
    messages = []
    for item in budget_history(history):
        content = (item.get("content") or "").strip()
        if not content:
            continue
        if item.get("role") == "student":
            messages.append(HumanMessage(content=content))
        else:
            messages.append(AIMessage(content=content))
    return messages
