"""Pipeline RAG tuyến tính: query prep → retrieval → generation → citation check.

Không còn LangGraph, router, verifier, NDJSON block. Mỗi request tối đa:
- 1 structured call cho query rewrite/HyDE (nếu cần)
- 1 streaming call cho câu trả lời
- 1 retry streaming nếu citation gate thất bại
"""

import logging
import re
import time
import unicodedata
from collections.abc import AsyncIterator
from contextlib import aclosing

from app.settings import lms_detection_enabled
from app.workflow import lms
from app.workflow.citations import has_valid_citation, strip_invalid_citations
from app.workflow.generation import stream_answer
from app.workflow.query import prepare_query
from app.workflow.retrieval import build_citations, get_retriever
from app.workflow.state import ChatState

logger = logging.getLogger(__name__)

_GREETINGS = {
    "xin chào",
    "chào",
    "chào bạn",
    "hello",
    "hi",
    "hey",
}
_THANKS = {"cảm ơn", "cảm ơn bạn", "thanks", "thank you"}
_HELP = {"bạn giúp được gì", "bạn làm được gì", "bạn có thể giúp gì"}

_NO_CITATION_OK = re.compile(
    r"(không tìm thấy|không có trong tài liệu|không chứa thông tin|"
    r"ngoài tài liệu môn học)",
    re.IGNORECASE,
)


def greeting_reply(question: str) -> str | None:
    """Chỉ match toàn bộ câu, để không nuốt câu hỏi có chủ đề."""
    text = unicodedata.normalize("NFC", question).lower().strip()
    text = re.sub(r"[.!?,;:]+$", "", text).strip()
    if text in _GREETINGS:
        return (
            "Chào bạn! Mình có thể giúp bạn tìm hiểu nội dung slide và hỗ trợ "
            "học tập trong khóa học."
        )
    if text in _THANKS:
        return "Không có gì! Bạn có thể hỏi tiếp về nội dung khóa học nhé."
    if text in _HELP:
        return (
            "Mình hỗ trợ giải thích nội dung slide, gợi ý trước khi nộp bài và "
            "chữa bài sau khi nộp."
        )
    return None


def _status(stage: str) -> dict:
    return {"event": "status", "data": {"stage": stage}}


def _token(state: ChatState, text: str) -> dict:
    state.answer += text
    return {"event": "token", "data": {"text": text}}


def _done(state: ChatState) -> dict:
    return {
        "event": "done",
        "data": {
            "intent": state.intent,
            "verified": state.verified,
            "routes": state.routes or ["knowledge"],
            "finish_reason": state.finish_reason,
            "citation_count": len(state.citations),
        },
    }


def _source_list(citations: list[dict]) -> str:
    if not citations:
        return ""
    lines = ["Nguồn tham khảo:"]
    for index, citation in enumerate(citations, start=1):
        title = citation.get("title") or "Tài liệu môn học"
        slide = citation.get("slide_index")
        suffix = f" (slide {slide})" if slide else ""
        lines.append(f"[{index}] {title}{suffix}")
    return "\n".join(lines)


def _allows_no_citation(text: str) -> bool:
    return bool(_NO_CITATION_OK.search(text or ""))


async def _stream_with_citation_gate(state: ChatState) -> AsyncIterator[dict]:
    """Phát token ngay khi có; hậu kiểm citation, không retry toàn câu.

    Nếu model không tự cite, chèn danh sách nguồn để câu trả lời cuối vẫn có
    citation hợp lệ. `verified` phản ánh câu trả lời cuối, không phải việc model
    có tự sinh citation hay không.
    """
    count = len(state.citations)
    text = ""
    cited = False
    started = time.perf_counter()
    first_chunk_at: float | None = None
    first_citation_at: float | None = None

    async with aclosing(stream_answer(state)) as source:
        async for chunk in source:
            if first_chunk_at is None:
                first_chunk_at = time.perf_counter()
            text += chunk
            if not cited and has_valid_citation(text, count):
                cited = True
                first_citation_at = time.perf_counter()
            yield _token(state, chunk)

    if cited:
        state.verified = True
        state.finish_reason = "stop"
    elif _allows_no_citation(text):
        state.verified = False
        state.finish_reason = "insufficient_evidence"
    else:
        sources = _source_list(state.citations)
        if sources:
            text += "\n\n" + sources
            yield _token(state, "\n\n" + sources)
            cited = has_valid_citation(text, count)
        state.verified = cited
        state.finish_reason = "citation_fallback" if cited else "citation_failed"
        logger.info(
            "citation_fallback citations=%s chars=%s", count, len(text)
        )

    logger.info(
        "chat_stream_ttft first_chunk_ms=%s first_citation_ms=%s",
        round((first_chunk_at - started) * 1000) if first_chunk_at else None,
        round((first_citation_at - started) * 1000) if first_citation_at else None,
    )


async def _run_chat(state: ChatState) -> AsyncIterator[dict]:
    started = time.perf_counter()

    # 1. Fast path cho lời chào/cảm ơn.
    reply = greeting_reply(state.question)
    if reply:
        yield _status("generating")
        yield _token(state, reply)
        state.intent = "general"
        state.routes = ["general"]
        yield _done(state)
        return

    # 2. LMS detection (regex, không LLM). Làm trước query prep để câu hỏi
    # thuần LMS không tốn thêm một LLM call.
    operation = lms.detect_operation(state.question) if lms_detection_enabled() else None
    if operation:
        try:
            data = await lms.query(state, operation)
            state.lms_data = data
            state.lms_text = lms.render(data, operation)
        except lms.AccessRevoked:
            raise
        except Exception:
            logger.warning("LMS query failed; continuing without LMS data", exc_info=True)

    if operation and lms.is_pure_lms(state.question) and state.lms_text:
        yield _status("generating")
        yield _token(state, state.lms_text)
        state.intent = "lms"
        state.routes = ["lms"]
        yield _done(state)
        return

    # 3. Query rewrite + HyDE adaptive.
    yield _status("rewriting")
    prep = await prepare_query(state)
    state.query = prep.query or state.question
    state.hyde = prep.hypothetical_answer
    state.used_hyde = bool(state.hyde)

    # 4. Retrieval.
    yield _status("retrieving")
    docs = await get_retriever().asearch(
        state.query,
        state.hyde,
        state.course_id,
    )
    # Không tin metadata để mở rộng phạm vi truy cập.
    if any(str(doc.get("course_id")) != str(state.course_id) for doc in docs):
        raise ValueError("Retrieval returned foreign course")

    state.retrieved_docs = docs
    state.citations = build_citations(docs)
    yield {"event": "citations", "data": {"citations": state.citations}}

    if not docs:
        text = (
            "Mình chưa tìm thấy nội dung phù hợp trong tài liệu môn học cho câu "
            "hỏi này. Bạn thử hỏi cụ thể hơn hoặc nêu tên bài/chương nhé."
        )
        yield _status("generating")
        yield _token(state, text)
        state.verified = False
        state.finish_reason = "insufficient_evidence"
        state.intent = "course_qa"
        state.routes = ["knowledge"]
        yield _done(state)
        return

    # 5. Generation + citation gate.
    yield _status("generating")
    async for event in _stream_with_citation_gate(state):
        yield event

    state.intent = "course_qa"
    state.routes = ["lms", "knowledge"] if state.lms_text else ["knowledge"]
    yield _status("checking_citations")
    yield _done(state)
    logger.info(
        "chat_complete seconds=%.3f hyde=%s docs=%s verified=%s finish=%s",
        time.perf_counter() - started,
        state.used_hyde,
        len(state.retrieved_docs),
        state.verified,
        state.finish_reason,
    )


async def run_chat(state: ChatState) -> AsyncIterator[dict]:
    """Chỉ phát các event SSE đã được kiểm soát."""
    try:
        async for event in _run_chat(state):
            yield event
    except Exception:
        logger.exception("Chat request failed")
        yield {
            "event": "error",
            "data": {
                "message": (
                    "Trợ lý tạm thời không thể hoàn tất. Vui lòng gửi lại câu hỏi."
                )
            },
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

    # Non-streaming: sanitize citation sai trước khi trả.
    answer_text = strip_invalid_citations(answer_text, len(citations))
    return answer_text, citations, intent, verified
