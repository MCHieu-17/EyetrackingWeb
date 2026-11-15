"""HTTP/SSE transport tới chatbot service."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress

import httpx

from app.core.config import settings

AccessCheck = Callable[[], Awaitable[None]]

_client_instance: httpx.AsyncClient | None = None


def ready() -> bool:
    return bool(settings.chatbot_url_resolved and settings.chatbot_internal_token)


def _client() -> httpx.AsyncClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = httpx.AsyncClient(
            timeout=settings.chatbot_timeout_seconds,
            headers={"X-Chatbot-Token": settings.chatbot_internal_token},
        )
    return _client_instance


async def close_client() -> None:
    global _client_instance
    if _client_instance is not None:
        await _client_instance.aclose()
        _client_instance = None


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def error_stream(message: str) -> AsyncIterator[str]:
    yield sse("error", {"message": message})


async def _guarded_lines(
    response: httpx.Response, ensure_access: AccessCheck
) -> AsyncIterator[str]:
    """Đọc SSE, gửi heartbeat và kiểm tra lại quyền khi stream im lặng."""
    lines = response.aiter_lines().__aiter__()
    pending = asyncio.create_task(anext(lines))
    try:
        while True:
            done, _ = await asyncio.wait({pending}, timeout=5)
            if not done:
                await ensure_access()
                yield ": heartbeat"
                continue
            try:
                line = pending.result()
            except StopAsyncIteration:
                return
            yield line
            pending = asyncio.create_task(anext(lines))
    finally:
        pending.cancel()
        with suppress(asyncio.CancelledError, StopAsyncIteration):
            await pending


async def stream_events(
    payload: dict, ensure_access: AccessCheck
) -> AsyncIterator[tuple[str, dict]]:
    """POST /chat/stream và tách các event SSE thành `(event, data)`."""
    async with _client().stream(
        "POST",
        f"{settings.chatbot_url_resolved.rstrip('/')}/chat/stream",
        json=payload,
    ) as response:
        response.raise_for_status()
        event = "message"
        async for line in _guarded_lines(response, ensure_access):
            if line.startswith("event: "):
                event = line[7:].strip()
                continue
            if not line.startswith("data: "):
                continue
            yield event, json.loads(line[6:])
