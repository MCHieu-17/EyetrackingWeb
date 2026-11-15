"""API chat: non-streaming và SSE.

Cả hai endpoint đều yêu cầu `X-Chatbot-Token` (backend gọi nội bộ). Chatbot
service không publish port ra ngoài trong docker-compose.
"""

import asyncio
import json
import logging
import os
import secrets
from contextlib import aclosing

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse

from app.schemas import ChatRequest, ChatResponse, CitationOut
from app.settings import internal_token
from app.workflow.pipeline import collect_chat, run_chat
from app.workflow.state import ChatState
from app.workflow.workload import chat_finished, chat_started

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

# Giới hạn số chat xử lý đồng thời ở tầng API. Khi vượt, trả 429 thay vì để
# hàng đợi asyncio phình vô hạn và làm tăng latency toàn bộ.
_CHAT_MAX_CONCURRENT = int(os.getenv("CHATBOT_MAX_CONCURRENT", "20"))
_CHAT_QUEUE_TIMEOUT = float(os.getenv("CHATBOT_QUEUE_TIMEOUT", "2"))
_chat_slots = asyncio.Semaphore(_CHAT_MAX_CONCURRENT)


async def _acquire_chat_slot() -> None:
    try:
        await asyncio.wait_for(
            _chat_slots.acquire(), timeout=_CHAT_QUEUE_TIMEOUT
        )
    except TimeoutError as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Chatbot đang quá tải, vui lòng thử lại.",
            headers={"Retry-After": "2"},
        ) from exc


def require_internal_token(x_chatbot_token: str = Header(default="")) -> None:
    expected = internal_token()
    if not expected or not secrets.compare_digest(x_chatbot_token, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


def _state_from_request(payload: ChatRequest) -> ChatState:
    return ChatState(
        question=payload.message,
        context_key=payload.context_key,
        course_id=payload.course_id,
        thread_id=payload.thread_id,
        history=[item.model_dump() for item in payload.history],
        lesson_id=payload.lesson_id,
        lesson_title=payload.lesson_title,
        module_title=payload.module_title,
        attempt_id=payload.attempt_id,
        assignment_id=payload.assignment_id,
        assignment_title=payload.assignment_title,
        assignment_context=payload.assignment_context,
        support_mode=payload.support_mode,
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post(
    "/chat",
    response_model=ChatResponse,
    dependencies=[Depends(require_internal_token)],
)
async def chat(payload: ChatRequest):
    """Nhận câu hỏi, chạy pipeline và trả câu trả lời kèm citations."""
    state = _state_from_request(payload)
    await _acquire_chat_slot()
    chat_started()
    try:
        answer, citations, intent, verified = await collect_chat(state)
    except RuntimeError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    finally:
        chat_finished()
        _chat_slots.release()

    return ChatResponse(
        answer=answer,
        citations=[CitationOut(**citation) for citation in citations],
        intent=intent,
        verified=verified,
        routes=state.routes,
        finish_reason=state.finish_reason,
    )


@router.post(
    "/chat/stream",
    dependencies=[Depends(require_internal_token)],
)
async def chat_stream(payload: ChatRequest):
    """SSE: status -> citations -> token -> done."""
    state = _state_from_request(payload)
    await _acquire_chat_slot()

    async def event_stream():
        chat_started()
        try:
            async with aclosing(run_chat(state)) as stream:
                async for event in stream:
                    yield _sse(event["event"], event["data"])
        finally:
            chat_finished()
            _chat_slots.release()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
