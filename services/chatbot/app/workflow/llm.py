"""Shared asynchronous LLM transport (OpenAI-compatible).

Chỉ còn hai loại call:
- `structured`: query rewrite/HyDE (JSON schema, max_tokens nhỏ).
- `stream`: sinh câu trả lời (streaming).

Server NEU dùng header `x-ollama-seckey` thay vì `Authorization: Bearer`.
Thinking của Qwen được tắt mặc định qua `chat_template_kwargs`.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from functools import lru_cache

import httpx
from openai import AsyncOpenAI, RateLimitError

from app import settings

logger = logging.getLogger(__name__)
_purpose = ContextVar("llm_purpose", default="unknown")


async def log_attempt(request):
    logger.info("llm_http_attempt purpose=%s", _purpose.get())


async def log_response(response):
    if response.status_code == 429:
        logger.warning("llm_http_429 purpose=%s", _purpose.get())


def messages(items):
    roles = {"human": "user", "ai": "assistant", "system": "system"}
    return [{"role": roles[item.type], "content": item.content} for item in items]


class LLMClient:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.neu_base_url(),
            api_key=settings.neu_api_key() or "not-needed",
            default_headers=settings.neu_headers(),
            max_retries=0,
            http_client=httpx.AsyncClient(
                limits=httpx.Limits(max_connections=40, max_keepalive_connections=40),
                event_hooks={"request": [log_attempt], "response": [log_response]},
            ),
        )
        self.generation = asyncio.Semaphore(settings.neu_generation_concurrency())
        self.total = asyncio.Semaphore(settings.neu_total_concurrency())
        self.rate_lock = asyncio.Lock()
        self.next_request = 0.0
        self.requests_per_second = settings.neu_requests_per_second()

    @asynccontextmanager
    async def slot(self, purpose):
        started = time.perf_counter()
        async with asyncio.timeout(settings.neu_queue_timeout()):
            await self.generation.acquire()
            try:
                await self.total.acquire()
            except BaseException:
                self.generation.release()
                raise
        logger.info(
            "llm_queue purpose=%s seconds=%.3f",
            purpose,
            time.perf_counter() - started,
        )
        purpose_token = _purpose.set(purpose)
        try:
            async with asyncio.timeout(settings.neu_queue_timeout()):
                if self.requests_per_second > 0:
                    async with self.rate_lock:
                        await asyncio.sleep(
                            max(0, self.next_request - time.monotonic())
                        )
                        self.next_request = (
                            time.monotonic() + 1 / self.requests_per_second
                        )
            timeout = {
                "query": settings.neu_query_timeout(),
                "answer": settings.neu_answer_timeout(),
            }.get(purpose, settings.neu_timeout())
            async with asyncio.timeout(timeout):
                yield
        except RateLimitError:
            logger.warning("llm_429 purpose=%s", purpose)
            raise
        finally:
            _purpose.reset(purpose_token)
            self.total.release()
            self.generation.release()

    def options(self, purpose):
        if purpose == "query":
            limit = settings.neu_query_max_tokens()
            temperature = 0.2
        else:
            limit = settings.answer_max_tokens()
            temperature = settings.answer_temperature()
        return {
            "model": settings.neu_llm_model(),
            "temperature": temperature,
            "max_tokens": limit,
            "extra_body": {
                "chat_template_kwargs": {
                    "enable_thinking": settings.neu_enable_thinking()
                }
            },
        }

    async def structured(self, purpose, prompt, schema):
        async with self.slot(purpose):
            client = self.client.with_options(max_retries=1)
            response = await client.chat.completions.create(
                **self.options(purpose),
                messages=prompt,
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "respond",
                            "description": "Return the requested structured result",
                            "parameters": schema.model_json_schema(),
                        },
                    }
                ],
                tool_choice={"type": "function", "function": {"name": "respond"}},
            )
            logger.info("llm_call purpose=%s usage=%s", purpose, response.usage)
            calls = response.choices[0].message.tool_calls or []
            if len(calls) != 1:
                raise ValueError("Missing structured response")
            return schema.model_validate_json(calls[0].function.arguments)

    async def stream(self, prompt):
        async with self.slot("answer"):
            # Retry only request creation; never replay a stream after it starts.
            stream = await self.client.with_options(max_retries=1).chat.completions.create(
                **self.options("answer"),
                messages=prompt,
                stream=True,
                stream_options={"include_usage": True},
            )
            try:
                async for chunk in stream:
                    if chunk.usage:
                        logger.info("llm_call purpose=answer usage=%s", chunk.usage)
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            finally:
                await stream.close()

    async def close(self):
        await self.client.close()


@lru_cache(maxsize=1)
def get_llm_client():
    return LLMClient()
