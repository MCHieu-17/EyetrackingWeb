#!/usr/bin/env python3
"""Đo retention gaze theo batch (gate Đợt 6).

Chạy trong image backend của stack benchmark:

    docker compose -p eyelearning-bench --env-file .env \
      -f docker-compose.yml -f benchmarks/stack/docker-compose.bench.yml \
      exec -T backend python /bench/backend/maintenance_probe.py \
      --old-samples 1000000 --batch-size 10000 \
      --out /bench/baseline/<run-id>/backend/maintenance_probe.json

Probe chỉ tạo/xoá dữ liệu tạm trong database `*_bench`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Khi chạy `python /bench/backend/maintenance_probe.py`, app nằm ở /app.
if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from sqlalchemy import event, text  # noqa: E402

from app.db.session import SessionLocal, engine  # noqa: E402
from app.maintenance import delete_old_gaze_samples  # noqa: E402


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-samples", type=int, default=1_000_000)
    parser.add_argument("--batch-size", type=int, default=10_000)
    parser.add_argument("--insert-batch", type=int, default=200)
    parser.add_argument("--insert-baseline-batches", type=int, default=5)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--allow-non-bench", action="store_true")
    return parser.parse_args()


async def _fixture(db) -> tuple[str, str]:
    row = (
        await db.execute(
            text(
                """
                SELECT e.id AS enrollment_id, s.id AS slide_id, s.lesson_id
                FROM enrollments e
                JOIN course_modules cm ON cm.course_id = e.course_id
                JOIN lessons l ON l.module_id = cm.id AND l.kind = 'lesson'
                JOIN slides s ON s.lesson_id = l.id
                LIMIT 1
                """
            )
        )
    ).first()
    if row is None:
        raise SystemExit("Không có enrollment/lesson/slide trong DB benchmark")
    return str(row.enrollment_id), str(row.slide_id), str(row.lesson_id)


async def _seed(
    db, enrollment_id: str, slide_id: str, lesson_id: str, samples: int
) -> tuple[str, str]:
    await db.execute(
        text("SELECT set_config('statement_timeout', '120000', true)")
    )
    session_id = str(uuid.uuid4())
    old_view_id = str(uuid.uuid4())
    live_view_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await db.execute(
        text(
            "INSERT INTO learning_sessions "
            "(id, enrollment_id, lesson_id, status, started_at, ended_at, expires_at) "
            "VALUES (CAST(:id AS uuid), CAST(:enrollment AS uuid), "
            "        CAST(:lesson AS uuid), 'completed', "
            "        CAST(:started AS timestamptz), CAST(:ended AS timestamptz), "
            "        CAST(:expires AS timestamptz))"
        ),
        {
            "id": session_id,
            "enrollment": enrollment_id,
            "lesson": lesson_id,
            "started": now - timedelta(days=500),
            "ended": now - timedelta(days=499),
            "expires": now + timedelta(hours=12),
        },
    )
    for view_id, sequence in ((old_view_id, 0), (live_view_id, 1)):
        await db.execute(
            text(
                "INSERT INTO content_views "
                "(id, session_id, slide_id, surface, sequence_no, started_at) "
                "VALUES (CAST(:id AS uuid), CAST(:session AS uuid), "
                "        CAST(:slide AS uuid), 'lesson', :sequence, "
                "        CAST(:started AS timestamptz))"
            ),
            {
                "id": view_id,
                "session": session_id,
                "slide": slide_id,
                "sequence": sequence,
                "started": now - timedelta(days=500),
            },
        )
    await db.execute(
        text(
            "INSERT INTO gaze_samples "
            "(content_view_id, client_batch_id, sequence, event_time, "
            " viewport_x, viewport_y, status, quality_flags) "
            "SELECT CAST(:view AS uuid), CAST(:batch AS uuid), g, "
            "       CAST(:event_time AS timestamptz), 0.5, 0.5, 'ok', '{}'::jsonb "
            "FROM generate_series(0, CAST(:count AS integer) - 1) AS g"
        ),
        {
            "view": old_view_id,
            "batch": str(uuid.uuid4()),
            "event_time": now - timedelta(days=400),
            "count": samples,
        },
    )
    await db.commit()
    return session_id, live_view_id


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))
    return round(ordered[index], 2)


async def _insert_loop(
    view_id: str,
    stop: asyncio.Event,
    times: list[float],
    *,
    batch: int,
    sequence_start: int = 0,
) -> int:
    sequence = sequence_start
    while not stop.is_set():
        started = time.perf_counter()
        async with SessionLocal() as db:
            await db.execute(
                text(
                    "INSERT INTO gaze_samples "
                    "(content_view_id, client_batch_id, sequence, event_time, "
                    " viewport_x, viewport_y, status, quality_flags) "
                    "SELECT CAST(:view AS uuid), CAST(:batch AS uuid), "
                    "       CAST(:start AS bigint) + g, now(), 0.5, 0.5, 'ok', "
                    "       '{}'::jsonb "
                    "FROM generate_series(0, CAST(:count AS integer) - 1) AS g"
                ),
                {
                    "view": view_id,
                    "batch": str(uuid.uuid4()),
                    "start": sequence,
                    "count": batch,
                },
            )
            await db.commit()
        sequence += batch
        times.append((time.perf_counter() - started) * 1000)
        try:
            await asyncio.wait_for(stop.wait(), timeout=1.5)
        except asyncio.TimeoutError:
            pass
    return sequence


async def _poll_lock_wait(stop: asyncio.Event, result: dict) -> None:
    max_seconds = 0.0
    while not stop.is_set():
        async with engine.connect() as conn:
            seconds = (
                await conn.execute(
                    text(
                        """
                        SELECT coalesce(
                            max(extract(epoch FROM now() - query_start)), 0
                        )
                        FROM pg_stat_activity
                        WHERE wait_event_type = 'Lock'
                          AND pid <> pg_backend_pid()
                        """
                    )
                )
            ).scalar_one()
        max_seconds = max(max_seconds, float(seconds or 0))
        try:
            await asyncio.wait_for(stop.wait(), timeout=0.02)
        except asyncio.TimeoutError:
            pass
    result["lock_wait_max_ms"] = round(max_seconds * 1000, 2)


async def _run(args: argparse.Namespace) -> dict:
    async with SessionLocal() as db:
        db_name = (await db.execute(text("SELECT current_database()"))).scalar_one()
        if not db_name.endswith("_bench") and not args.allow_non_bench:
            raise SystemExit(
                f"Từ chối chạy trên database {db_name!r}; "
                "dùng --allow-non-bench nếu thật sự cần"
            )
        enrollment_id, slide_id, lesson_id = await _fixture(db)
        session_id, live_view_id = await _seed(
            db, enrollment_id, slide_id, lesson_id, args.old_samples
        )

    insert_times: list[float] = []
    baseline_stop = asyncio.Event()
    baseline_task = asyncio.create_task(
        _insert_loop(
            live_view_id,
            baseline_stop,
            insert_times,
            batch=args.insert_batch,
        )
    )
    for _ in range(max(0, args.insert_baseline_batches)):
        try:
            await asyncio.wait_for(baseline_stop.wait(), timeout=1.5)
        except asyncio.TimeoutError:
            pass
    baseline_stop.set()
    await baseline_task
    baseline_times = list(insert_times)

    txn_start: dict[int, float] = {}
    txn_times: list[float] = []

    def on_begin(conn) -> None:
        txn_start[id(conn)] = time.perf_counter()

    def on_commit(conn) -> None:
        started = txn_start.pop(id(conn), None)
        if started is not None:
            txn_times.append((time.perf_counter() - started) * 1000)

    def on_rollback(conn) -> None:
        txn_start.pop(id(conn), None)

    event.listen(engine.sync_engine, "begin", on_begin)
    event.listen(engine.sync_engine, "commit", on_commit)
    event.listen(engine.sync_engine, "rollback", on_rollback)

    lock_result: dict = {}
    lock_stop = asyncio.Event()
    lock_task = asyncio.create_task(_poll_lock_wait(lock_stop, lock_result))

    insert_times.clear()
    during_stop = asyncio.Event()
    during_task = asyncio.create_task(
        _insert_loop(
            live_view_id,
            during_stop,
            insert_times,
            batch=args.insert_batch,
            sequence_start=baseline_task.result(),
        )
    )

    try:
        started = time.perf_counter()
        async with SessionLocal() as db:
            deleted = await delete_old_gaze_samples(
                db, batch_size=max(1, args.batch_size)
            )
        delete_wall_ms = (time.perf_counter() - started) * 1000
    finally:
        during_stop.set()
        await during_task
        lock_stop.set()
        await lock_task
        event.remove(engine.sync_engine, "begin", on_begin)
        event.remove(engine.sync_engine, "commit", on_commit)
        event.remove(engine.sync_engine, "rollback", on_rollback)

    during_times = list(insert_times)
    p95_base = _percentile(baseline_times, 95)
    p95_during = _percentile(during_times, 95)
    increase = (
        round((p95_during - p95_base) / p95_base * 100, 1) if p95_base else 0.0
    )

    if not args.keep:
        async with SessionLocal() as db:
            await db.execute(
                text("DELETE FROM learning_sessions WHERE id = :id"),
                {"id": session_id},
            )
            await db.commit()

    return {
        "database": db_name,
        "old_samples": args.old_samples,
        "batch_size": args.batch_size,
        "deleted": deleted,
        "expected_batches": (
            (args.old_samples + args.batch_size - 1) // args.batch_size
        ),
        "delete_wall_ms": round(delete_wall_ms, 1),
        "max_transaction_ms": round(max(txn_times, default=0.0), 1),
        "commits": len(txn_times),
        **lock_result,
        "insert_baseline": {
            "count": len(baseline_times),
            "p50_ms": _percentile(baseline_times, 50),
            "p95_ms": p95_base,
        },
        "insert_during_delete": {
            "count": len(during_times),
            "p50_ms": _percentile(during_times, 50),
            "p95_ms": p95_during,
        },
        "insert_p95_increase_pct": increase,
    }


def main() -> None:
    args = _args()
    result = asyncio.run(_run(args))
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n")
    print(payload)


if __name__ == "__main__":
    main()
