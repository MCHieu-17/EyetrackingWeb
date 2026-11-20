"""Adapter mỏng gọi entrypoint worker hiện có (một lượt)."""

from __future__ import annotations

from app.services.analysis import execute_pending_runs
from app.services.content import process_pending_slide_imports
from app.services.embedding_jobs import process_pending_jobs


async def run_analysis(limit: int = 10) -> int:
    return await execute_pending_runs(limit=limit)


async def run_slide_imports(limit: int = 1) -> int:
    return await process_pending_slide_imports(limit=limit)


async def run_index_jobs(limit: int = 1) -> int:
    return await process_pending_jobs(limit=limit)
