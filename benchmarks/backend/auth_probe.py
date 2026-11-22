#!/usr/bin/env python3
"""Đo auth memory-hit (Phase 9): p95 và số Redis GET mỗi lần gọi.

Chạy trong image backend (có app + asyncpg):
    python /bench/backend/auth_probe.py \
      --fixtures /bench/baseline/<run>/fixtures.json \
      --iterations 500 \
      --out /bench/baseline/<run>/backend/auth_probe.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

# Khi chạy `python /bench/backend/auth_probe.py`, sys.path chỉ có thư mục
# script; app nằm ở /app trong image backend.
if "/app" not in sys.path:
    sys.path.insert(0, "/app")


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(pct / 100 * (len(ordered) - 1))))
    return ordered[index]


def _get_calls(info: dict | None) -> int:
    entry = (info or {}).get("cmdstat_get")
    if isinstance(entry, dict):
        return int(entry.get("calls", 0) or 0)
    raw = entry or ""
    if isinstance(raw, str):
        for part in raw.split(","):
            if part.startswith("calls="):
                return int(part.split("=", 1)[1])
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", required=True)
    parser.add_argument("--iterations", type=int, default=500)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    from app.crud.user import _AUTH_MEMORY, get_user_for_auth_cached
    from app.db.redis import get_redis
    from app.db.session import SessionLocal

    fixtures = json.loads(Path(args.fixtures).read_text(encoding="utf-8"))
    user_id = fixtures["student_ids"][0]
    memory_key = f"auth:user:{user_id}"

    client = await get_redis()

    async with SessionLocal() as db:
        # Warm Redis/DB như request đầu tiên của worker.
        await get_user_for_auth_cached(db, user_id)
        # Xoá memory để lần gọi kế đi qua nhánh Redis-hit và phải nạp lại memory.
        _AUTH_MEMORY.pop(memory_key, None)
        await get_user_for_auth_cached(db, user_id)

        before = _get_calls(await client.info("commandstats")) if client else 0
        durations: list[float] = []
        for _ in range(args.iterations):
            started = time.perf_counter()
            await get_user_for_auth_cached(db, user_id)
            durations.append((time.perf_counter() - started) * 1000)
        after = _get_calls(await client.info("commandstats")) if client else 0

    redis_gets = max(0, after - before)
    result = {
        "user_id": user_id,
        "iterations": args.iterations,
        "p50_ms": percentile(durations, 50),
        "p95_ms": percentile(durations, 95),
        "p99_ms": percentile(durations, 99),
        "redis_get_calls": redis_gets,
        "redis_get_per_call": round(redis_gets / args.iterations, 6),
        "memory_entries": len(_AUTH_MEMORY),
    }
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
