"""Graph orchestration helpers and API collection.

Không dùng checkpointer: backend gửi history theo từng request và là nguồn sự
thật cho lịch sử hiển thị. Pipeline chỉ giữ state trong bộ nhớ của request.

Streaming emits only complete approved blocks.
"""

import logging
import re
from collections.abc import AsyncIterator
from contextlib import aclosing

from app.workflow.state import ChatState

logger = logging.getLogger(__name__)


def _status(stage: str) -> dict:
    return {"event": "status", "data": {"stage": stage}}


def retrieval_query(state: ChatState) -> str:
    """Resolve references like 'câu cuối' using trusted server quiz prompts."""
    question = state["question"]
    prompts = {
        int(n): prompt
        for n, prompt in re.findall(
            r"^Câu (\d+): ([^\n]+)", state.get("assignment_context") or "", re.MULTILINE
        )
    }
    if not prompts:
        return question
    requested = {int(n) for n in re.findall(r"câu\s*(\d+)", question, re.IGNORECASE)}
    lower = question.lower()
    numbers = sorted(prompts)
    if "câu cuối" in lower:
        requested.add(numbers[-1])
    if "câu đầu" in lower:
        requested.add(numbers[0])
    if "câu giữa" in lower:
        requested.add(numbers[(len(numbers) - 1) // 2])
    selected = (
        [prompts[n] for n in numbers if n in requested] if requested else list(prompts.values())
    )
    # Only the search query has a bound; the answer/verifier still see ALL quiz data.
    return question + "\nChủ đề câu hỏi trong bài tập: " + "\n".join(selected)[:8000]


def assignment_overview(state: ChatState) -> str | None:
    """Repeat public question wording exactly; summarizing yes/no questions can leak a conclusion."""
    context = state.get("assignment_context") or ""
    prompts = {
        int(n): prompt for n, prompt in re.findall(r"^Câu (\d+): ([^\n]+)", context, re.MULTILINE)
    }
    lower = state["question"].lower()
    if not prompts or not ("bao nhiêu câu" in lower or "số câu hỏi" in lower):
        return None
    numbers = sorted(prompts)
    lines = [f"Đề có {len(prompts)} câu hỏi."]
    # Use full question wording, preserving question marks and uncertainty.
    requested = []
    for phrase, number in (
        ("câu đầu", numbers[0]),
        ("câu giữa", numbers[(len(numbers) - 1) // 2]),
        ("câu cuối", numbers[-1]),
    ):
        if phrase in lower:
            requested.append(number)
    for number in dict.fromkeys(requested):
        lines.append(f"- Câu {number}: {prompts[number]}")
    return "\n".join(lines)


async def run_chat(state: ChatState) -> AsyncIterator[dict]:
    """Only approved, explicitly selected custom graph events reach callers."""
    from app.workflow.graph import stream_graph
    try:
        async with aclosing(stream_graph(state)) as stream:
            async for event in stream:
                if event["event"] == "done":
                    state.update(event["data"])
                yield event
    except Exception:
        logger.exception("Graph request failed")
        yield {"event": "error", "data": {"message": "Trợ lý tạm thời không thể hoàn tất. Vui lòng gửi lại câu hỏi."}}


async def collect_chat(state: ChatState) -> tuple[str, list[dict], str, bool]:
    """Chạy pipeline không stream; trả (answer, citations, intent, verified)."""
    answer_text = ""
    citations: list[dict] = []
    intent = "course_qa"
    verified = True

    async for event in run_chat(state):
        if event["event"] == "token":
            answer_text += event["data"]["text"]
        elif event["event"] == "citations":
            citations = event["data"]["citations"]
        elif event["event"] == "done":
            intent = event["data"]["intent"]
            verified = event["data"]["verified"]
        elif event["event"] == "error":
            raise RuntimeError(event["data"]["message"])

    return answer_text, citations, intent, verified
