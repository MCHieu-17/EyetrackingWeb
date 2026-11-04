"""API chat: non-streaming và SSE.

Cả hai endpoint đều yêu cầu `X-Chatbot-Token` (backend gọi nội bộ). Chatbot
service không publish port ra ngoài trong docker-compose.
"""

import json
import logging
import secrets
from contextlib import aclosing

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse

from app.schemas import ChatRequest, ChatResponse, CitationOut
from app.settings import internal_token
from app.workflow.pipeline import collect_chat, run_chat
from app.workflow.state import ChatState

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


def require_internal_token(x_chatbot_token: str = Header(default="")) -> None:
    expected = internal_token()
    if not expected or not secrets.compare_digest(x_chatbot_token, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


def _state_from_request(payload: ChatRequest) -> ChatState:
    return {
        "question": payload.message,
        "context_key": payload.context_key,
        "course_id": payload.course_id,
        "thread_id": payload.thread_id,
        "history": [item.model_dump() for item in payload.history],
        "lesson_id": payload.lesson_id,
        "lesson_title": payload.lesson_title,
        "module_title": payload.module_title,
        "assignment_id": payload.assignment_id,
        "assignment_title": payload.assignment_title,
        "assignment_context": payload.assignment_context,
        "support_mode": payload.support_mode,
        "attempts": 0,
    }


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
    try:
        answer, citations, intent, verified = await collect_chat(state)
    except RuntimeError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    return ChatResponse(
        answer=answer,
        citations=[CitationOut(**citation) for citation in citations],
        intent=intent,
        verified=verified,
        routes=state.get("routes", []),
        finish_reason=state.get("finish_reason", "stop"),
    )


@router.post(
    "/chat/stream",
    dependencies=[Depends(require_internal_token)],
)
async def chat_stream(payload: ChatRequest):
    """SSE: status -> citations -> token (sau verify) -> done."""
    state = _state_from_request(payload)

    async def event_stream():
        async with aclosing(run_chat(state)) as stream:
            async for event in stream:
                yield _sse(event["event"], event["data"])

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
