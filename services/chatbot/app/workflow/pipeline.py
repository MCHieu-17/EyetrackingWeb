"""Pipeline RAG: route -> retrieve -> answer -> verify -> stream.

Không dùng checkpointer: backend gửi history theo từng request và là nguồn sự
thật cho lịch sử hiển thị. Pipeline chỉ giữ state trong bộ nhớ của request.

Streaming: sau khi verify xong mới phát `token`; trước đó phát `status` để
frontend biết đang ở bước nào. Đây là lựa chọn "status + stream sau verify".
"""

import asyncio
import logging
from collections.abc import AsyncIterator

from app.settings import citation_max_attempts
from app.workflow.answer import RETRIEVAL_INTENTS, answer
from app.workflow.citations import chunk_text, sanitize_citations
from app.workflow.guardrails import safe_response, verify_answer
from app.workflow.retrieval import build_citations, get_retriever
from app.workflow.router import route
from app.workflow.state import ChatState

logger = logging.getLogger(__name__)


def _status(stage: str) -> dict:
    return {"event": "status", "data": {"stage": stage}}


async def run_chat(state: ChatState) -> AsyncIterator[dict]:
    """Chạy pipeline và yield các SSE event dict."""
    try:
        yield _status("routing")
        intent = await asyncio.to_thread(route, state)
        state["intent"] = intent

        if intent in RETRIEVAL_INTENTS:
            yield _status("retrieving")
            docs = await asyncio.to_thread(
                lambda: get_retriever().search(state["question"], state["course_id"])
            )
            state["retrieved_docs"] = docs
            state["citations"] = build_citations(docs)
        else:
            state["retrieved_docs"] = []
            state["citations"] = []

        yield _status("generating")
        draft = await asyncio.to_thread(answer, state)

        verified = True
        if intent in RETRIEVAL_INTENTS:
            max_attempts = citation_max_attempts()
            for attempt in range(1, max_attempts + 1):
                yield _status("verifying")
                verification = await asyncio.to_thread(verify_answer, state, draft)
                state["verification"] = verification
                if verification["ok"]:
                    break
                logger.info(
                    "Citation verification thất bại (lần %s): %s",
                    attempt,
                    verification.get("feedback", ""),
                )
                if attempt >= max_attempts:
                    logger.info(
                        "Citation verification thất bại sau %s lần — trả câu an toàn",
                        attempt,
                    )
                    draft = safe_response(intent)
                    verified = False
                    break
                yield _status("retrying")
                state["attempts"] = attempt
                state["verification_feedback"] = verification["feedback"]
                draft = await asyncio.to_thread(answer, state)

        final = sanitize_citations(draft, state["citations"])
        state["answer"] = final
        state["verified"] = verified

        yield {"event": "citations", "data": {"citations": state["citations"]}}
        for chunk in chunk_text(final):
            yield {"event": "token", "data": {"text": chunk}}
        yield {
            "event": "done",
            "data": {
                "intent": intent,
                "verified": verified,
                "citation_count": len(state["citations"]),
            },
        }
    except Exception:
        logger.exception("Chat pipeline lỗi")
        yield {
            "event": "error",
            "data": {"message": "Trợ lý học tập tạm thời không phản hồi."},
        }


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
