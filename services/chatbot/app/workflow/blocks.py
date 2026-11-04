"""Bounded generation and cumulative verification. Only approved blocks leave here."""

import asyncio
import logging
import re
import time

logger = logging.getLogger(__name__)
from contextlib import aclosing, suppress

from app.workflow.answer import answer_blocks
from app.workflow.guardrails import safe_response, verify_answer_async


def unavailable(state, approved, block_id):
    text = (
        "\n\n" if approved else ""
    ) + "Dịch vụ AI đang quá tải hoặc chưa thể kiểm chứng phần tiếp theo. Bạn vui lòng thử lại sau."
    state.update(answer=approved + text, verified=False, finish_reason="provider_unavailable")
    return {"event": "token", "data": {"text": text, "route": "knowledge", "block_id": block_id}}


async def verified_blocks(state):
    approved = ""
    generation_started = time.perf_counter()
    first_generated = False
    repaired = False
    block_id = 0
    while True:
        queue = asyncio.Queue(maxsize=2)

        async def produce():
            try:
                async with aclosing(answer_blocks(state)) as source:
                    async for block in source:
                        await queue.put(block)
            except Exception as exc:
                await queue.put(exc)
            else:
                await queue.put(None)

        producer = asyncio.create_task(produce())
        failed = False
        try:
            while True:
                block = await queue.get()
                if block is None:
                    if approved:
                        return
                    failed, feedback = True, "Model không trả đoạn nội dung nào."
                    break
                if isinstance(block, Exception):
                    if not isinstance(block, ValueError):
                        yield unavailable(state, approved, block_id)
                        return
                    failed = True
                    feedback = "Không đọc được đoạn hoàn chỉnh từ model."
                    break
                if not first_generated:
                    logger.info(
                        "chat_first_generated_block seconds=%.3f",
                        time.perf_counter() - generation_started,
                    )
                    first_generated = True
                candidate = approved + ("\n\n" if approved else "") + block
                ids = [int(n) for n in re.findall(r"\[(\d+)\]", block)]
                valid = all(1 <= n <= len(state.get("citations", [])) for n in ids)
                started = time.perf_counter()
                result = (
                    await verify_answer_async(state, candidate)
                    if valid
                    else {"ok": False, "feedback": "Citation không tồn tại."}
                )
                logger.info(
                    "chat_verify block=%s seconds=%.3f accepted=%s",
                    block_id,
                    time.perf_counter() - started,
                    result["ok"],
                )
                if result.get("provider_error"):
                    yield unavailable(state, approved, block_id)
                    return
                if not result["ok"]:
                    logger.info(
                        "chat_block_rejected block=%s repaired=%s feedback=%s",
                        block_id,
                        repaired,
                        result.get("feedback", ""),
                    )
                    failed = True
                    feedback = result["feedback"]
                    break
                text = ("\n\n" if approved else "") + block
                approved = candidate
                state["answer"] = approved
                yield {
                    "event": "token",
                    "data": {"text": text, "route": "knowledge", "block_id": block_id},
                }
                block_id += 1
        finally:
            producer.cancel()
            with suppress(asyncio.CancelledError):
                await producer
        if failed:
            if not repaired:
                repaired = True
                state["verification_feedback"] = feedback
                continue
            state["verified"] = False
            state["finish_reason"] = "verification_failed"
            state["answer"] = (
                approved + ("\n\n" if approved else "") + safe_response(state["intent"])
            )
            yield {
                "event": "token",
                "data": {
                    "text": ("\n\n" if approved else "") + safe_response(state["intent"]),
                    "route": "knowledge",
                    "block_id": block_id,
                },
            }
            return
