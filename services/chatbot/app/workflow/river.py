"""Shared asynchronous River transport with reserved verifier capacity."""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from functools import lru_cache

import httpx
from openai import AsyncOpenAI, RateLimitError

from app import settings

logger = logging.getLogger(__name__)
_purpose = ContextVar("river_purpose", default="unknown")


async def log_attempt(request):
    logger.info("river_http_attempt purpose=%s", _purpose.get())


async def log_response(response):
    if response.status_code == 429:
        logger.warning("river_http_429 purpose=%s", _purpose.get())


def messages(items):
    roles = {"human": "user", "ai": "assistant", "system": "system"}
    return [{"role": roles[item.type], "content": item.content} for item in items]


class River:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.river_base_url(),
            api_key=settings.river_api_key(),
            max_retries=0,
            http_client=httpx.AsyncClient(
                limits=httpx.Limits(max_connections=40, max_keepalive_connections=40),
                event_hooks={"request": [log_attempt], "response": [log_response]},
            ),
        )
        self.generation = asyncio.Semaphore(int(os.getenv("RIVER_GENERATION_CONCURRENCY", "4")))
        self.verification = asyncio.Semaphore(int(os.getenv("RIVER_VERIFY_CONCURRENCY", "2")))

        self.total = asyncio.Semaphore(int(os.getenv("RIVER_TOTAL_CONCURRENCY", "6")))
        self.rate_lock = asyncio.Lock()
        self.next_request = 0.0
        self.requests_per_second = float(os.getenv("RIVER_REQUESTS_PER_SECOND", "1"))

    @asynccontextmanager
    async def slot(self, purpose):
        started = time.perf_counter()
        semaphore = self.verification if purpose == "verify" else self.generation
        async with asyncio.timeout(float(os.getenv("RIVER_QUEUE_TIMEOUT", "30"))):
            await semaphore.acquire()
            try:
                await self.total.acquire()
            except BaseException:
                semaphore.release()
                raise
        logger.info("river_queue purpose=%s seconds=%.3f", purpose, time.perf_counter() - started)
        purpose_token = _purpose.set(purpose)
        try:
            async with asyncio.timeout(float(os.getenv("RIVER_QUEUE_TIMEOUT", "30"))):
                async with self.rate_lock:
                    await asyncio.sleep(max(0, self.next_request - time.monotonic()))
                    self.next_request = time.monotonic() + 1 / self.requests_per_second
            async with asyncio.timeout(
                float(
                    os.getenv(
                        f"RIVER_{purpose.upper()}_TIMEOUT", "60" if purpose != "router" else "15"
                    )
                )
            ):
                yield
        except RateLimitError:
            logger.warning("river_429 purpose=%s", purpose)
            raise
        finally:
            _purpose.reset(purpose_token)
            self.total.release()
            semaphore.release()

    def options(self, purpose):
        effort = settings.river_reasoning_effort()
        limit = min(settings.river_llm_max_tokens(), 2048)
        if purpose == "router":
            effort, limit = (
                settings.river_router_reasoning_effort(),
                max(512, settings.river_router_max_tokens()),
            )
        elif purpose == "verify":
            effort, limit = (
                settings.river_verifier_reasoning_effort(),
                settings.river_verifier_max_tokens(),
            )
        return {
            "model": settings.river_llm_model(),
            "temperature": 0,
            "max_tokens": limit,
            **({"extra_body": {"reasoning_effort": effort}} if effort else {}),
        }

    async def structured(self, purpose, prompt, schema):
        async with self.slot(purpose):
            client = self.client if purpose == "router" else self.client.with_options(max_retries=1)
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
            logger.info("river_call purpose=%s usage=%s", purpose, response.usage)
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
                        logger.info("river_call purpose=answer usage=%s", chunk.usage)
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            finally:
                await stream.close()

    async def close(self):
        await self.client.close()


@lru_cache(maxsize=1)
def get_river():
    return River()
