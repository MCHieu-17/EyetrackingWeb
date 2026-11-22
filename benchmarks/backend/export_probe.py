#!/usr/bin/env python3
"""Đo export JSONL + page `/teacher/visits/{id}/gaze` (gate Đợt 6).

Chạy trong image backend của stack benchmark:

    docker compose -p eyelearning-bench --env-file .env \
      -f docker-compose.yml -f benchmarks/stack/docker-compose.bench.yml \
      exec -T backend python /bench/backend/export_probe.py \
      --samples 100000 --concurrency 5 \
      --out /bench/baseline/<run-id>/backend/export_probe_100k.json

Probe chỉ tạo/xoá dữ liệu tạm trong database `*_bench`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import resource
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Khi chạy `python /bench/backend/export_probe.py`, app nằm ở /app.
if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from sqlalchemy import event, select, text, tuple_  # noqa: E402

from app.db.session import SessionLocal, engine  # noqa: E402
from app.models.gaze import GazeSample  # noqa: E402
from app.services.analysis import export_visit_lines  # noqa: E402
from app.services.analysis.export import VISIT_SAMPLE_SQL  # noqa: E402


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=100_000)
    parser.add_argument("--views", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--page-limit", type=int, default=1000)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--allow-non-bench", action="store_true")
    return parser.parse_args()


async def _fixture(db) -> tuple[str, str, str]:
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
    db, enrollment_id: str, slide_id: str, lesson_id: str, *, samples: int, views: int
) -> tuple[str, list[str]]:
    await db.execute(
        text("SELECT set_config('statement_timeout', '120000', true)")
    )
    visit_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await db.execute(
        text(
            "INSERT INTO course_visits "
            "(id, enrollment_id, started_at, ended_at, last_seen_at, status, visit_key) "
            "VALUES (CAST(:id AS uuid), CAST(:enrollment AS uuid), "
            "        CAST(:started AS timestamptz), CAST(:ended AS timestamptz), "
            "        CAST(:ended AS timestamptz), 'ended', :visit_key)"
        ),
        {
            "id": visit_id,
            "enrollment": enrollment_id,
            "started": now - timedelta(hours=2),
            "ended": now - timedelta(hours=1),
            "visit_key": f"probe-{visit_id}",
        },
    )
    await db.execute(
        text(
            "INSERT INTO learning_sessions "
            "(id, enrollment_id, lesson_id, course_visit_id, status, "
            " started_at, ended_at, expires_at) "
            "VALUES (CAST(:id AS uuid), CAST(:enrollment AS uuid), "
            "        CAST(:lesson AS uuid), CAST(:visit AS uuid), 'completed', "
            "        CAST(:started AS timestamptz), CAST(:ended AS timestamptz), "
            "        CAST(:expires AS timestamptz))"
        ),
        {
            "id": session_id,
            "enrollment": enrollment_id,
            "lesson": lesson_id,
            "visit": visit_id,
            "started": now - timedelta(hours=2),
            "ended": now - timedelta(hours=1),
            "expires": now + timedelta(hours=12),
        },
    )

    view_ids: list[str] = []
    base = now - timedelta(days=2)
    per_view = max(1, samples // max(1, views))
    remaining = samples
    for index in range(views):
        count = per_view if index < views - 1 else remaining
        remaining -= count
        view_id = str(uuid.uuid4())
        view_ids.append(view_id)
        await db.execute(
            text(
                "INSERT INTO content_views "
                "(id, session_id, slide_id, surface, sequence_no, started_at, ended_at) "
                "VALUES (CAST(:id AS uuid), CAST(:session AS uuid), "
                "        CAST(:slide AS uuid), 'lesson', :sequence, "
                "        CAST(:started AS timestamptz), CAST(:ended AS timestamptz))"
            ),
            {
                "id": view_id,
                "session": session_id,
                "slide": slide_id,
                "sequence": index,
                "started": base + timedelta(minutes=index),
                "ended": base + timedelta(minutes=index + 1),
            },
        )
        await db.execute(
            text(
                "INSERT INTO gaze_samples "
                "(content_view_id, client_batch_id, sequence, event_time, "
                " viewport_x, viewport_y, status, quality_flags) "
                "SELECT CAST(:view AS uuid), CAST(:batch AS uuid), g, "
                "       CAST(:base AS timestamptz) + "
                "       make_interval(secs => CAST(g * 0.066 AS double precision)), "
                "       CAST(0.2 + (g % 50) / 100.0 AS real), "
                "       CAST(0.2 + (g % 37) / 100.0 AS real), "
                "       'ok', '{}'::jsonb "
                "FROM generate_series(0, CAST(:count AS integer) - 1) AS g"
            ),
            {
                "view": view_id,
                "batch": str(uuid.uuid4()),
                "base": base + timedelta(minutes=index),
                "count": count,
            },
        )
    await db.commit()
    return visit_id, view_ids


async def _consume(source) -> tuple[int, int]:
    lines = 0
    size = 0
    async for line in source:
        lines += 1
        size += len(line)
    return lines, size


class _SqlTimer:
    def __init__(self) -> None:
        self.page_times: list[float] = []
        self._started: dict[int, float] = {}

    def before(self, conn, cursor, statement, parameters, context, executemany):
        if "gaze_samples" in statement and "LIMIT" in statement:
            self._started[id(conn)] = time.perf_counter()

    def after(self, conn, cursor, statement, parameters, context, executemany):
        started = self._started.pop(id(conn), None)
        if started is None:
            return
        if "gaze_samples" in statement and "LIMIT" in statement:
            self.page_times.append((time.perf_counter() - started) * 1000)


async def _poll_idle_in_transaction(stop: asyncio.Event, result: dict) -> None:
    max_count = 0
    max_seconds = 0.0
    while not stop.is_set():
        async with engine.connect() as conn:
            count, age = (
                await conn.execute(
                    text(
                        """
                        SELECT count(*),
                               coalesce(max(extract(epoch FROM now() - xact_start)), 0)
                        FROM pg_stat_activity
                        WHERE state = 'idle in transaction'
                          AND xact_start IS NOT NULL
                          AND now() - xact_start > interval '1 second'
                          AND pid <> pg_backend_pid()
                        """
                    )
                )
            ).one()
        max_count = max(max_count, int(count or 0))
        max_seconds = max(max_seconds, float(age or 0))
        try:
            await asyncio.wait_for(stop.wait(), timeout=0.05)
        except asyncio.TimeoutError:
            pass
    result["idle_in_transaction_max"] = max_count
    result["idle_in_transaction_max_seconds"] = round(max_seconds, 3)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))
    return round(ordered[index], 2)


def _rss_mib() -> float:
    with open("/proc/self/status", encoding="utf-8") as status:
        for line in status:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    return 0.0


async def _sample_cursor(db, view_ids: list[str], offset: int):
    return (
        await db.execute(
            select(GazeSample.event_time, GazeSample.id)
            .where(GazeSample.content_view_id.in_(view_ids))
            .order_by(GazeSample.event_time, GazeSample.id)
            .offset(offset)
            .limit(1)
        )
    ).first()


async def _gaze_page(
    db, view_ids: list[str], cursor, *, limit: int
) -> dict:
    if cursor is None:
        return {"samples": 0}

    stmt = (
        select(GazeSample.id, GazeSample.event_time)
        .where(GazeSample.content_view_id.in_(view_ids))
        .order_by(GazeSample.event_time, GazeSample.id)
        .limit(limit)
    )
    stmt = stmt.where(
        tuple_(GazeSample.event_time, GazeSample.id) > (cursor[0], cursor[1])
    )

    times: list[float] = []
    for _ in range(20):
        started = time.perf_counter()
        await db.execute(stmt)
        times.append((time.perf_counter() - started) * 1000)
        await db.commit()

    plan = "\n".join(
        (
            await db.execute(
                text(
                    "EXPLAIN (ANALYZE, BUFFERS) "
                    + str(stmt.compile(compile_kwargs={"literal_binds": True}))
                )
            )
        ).scalars()
    )
    return {
        "p50_ms": _percentile(times, 50),
        "p95_ms": _percentile(times, 95),
        "seq_scan_gaze_samples": "Seq Scan on gaze_samples" in plan,
    }


LEGACY_GAZE_SQL = """
SELECT gs.id, gs.event_time
FROM gaze_samples gs
JOIN content_views cv ON cv.id = gs.content_view_id
JOIN learning_sessions ls ON ls.id = cv.session_id
WHERE ls.course_visit_id = CAST(:visit_id AS UUID)
ORDER BY gs.event_time, gs.sequence
OFFSET :offset
LIMIT :limit
"""

LEGACY_EXPORT_SQL = """
SELECT gs.id, gs.event_time
FROM gaze_samples gs
JOIN content_views cv ON cv.id = gs.content_view_id
JOIN learning_sessions ls ON ls.id = cv.session_id
WHERE ls.course_visit_id = CAST(:visit_id AS UUID)
ORDER BY gs.event_time, gs.id
LIMIT :limit
"""

LEGACY_EXPORT_AFTER_SQL = LEGACY_EXPORT_SQL.replace(
    "WHERE ls.course_visit_id = CAST(:visit_id AS UUID)",
    "WHERE ls.course_visit_id = CAST(:visit_id AS UUID) "
    "AND (gs.event_time, gs.id) > "
    "(CAST(:after_time AS TIMESTAMPTZ), CAST(:after_id AS BIGINT))",
)


async def _timed(db, sql: str, params: dict, runs: int = 5) -> dict:
    times: list[float] = []
    for _ in range(runs):
        started = time.perf_counter()
        await db.execute(text(sql), params)
        times.append((time.perf_counter() - started) * 1000)
        await db.commit()
    return {
        "p50_ms": _percentile(times, 50),
        "p95_ms": _percentile(times, 95),
    }


async def _legacy_pages(db, visit_id: str, cursor, *, samples: int, limit: int) -> dict:
    offset = max(0, samples // 2)
    gaze = await _timed(
        db,
        LEGACY_GAZE_SQL,
        {"visit_id": visit_id, "offset": offset, "limit": limit},
    )
    export_first = await _timed(
        db, LEGACY_EXPORT_SQL, {"visit_id": visit_id, "limit": limit}
    )
    export_after = await _timed(
        db,
        LEGACY_EXPORT_AFTER_SQL,
        {
            "visit_id": visit_id,
            "limit": limit,
            "after_time": cursor[0] if cursor else None,
            "after_id": cursor[1] if cursor else 0,
        },
    )
    return {
        "gaze_offset": offset,
        "gaze_offset_p50_ms": gaze["p50_ms"],
        "gaze_offset_p95_ms": gaze["p95_ms"],
        "export_first_p50_ms": export_first["p50_ms"],
        "export_first_p95_ms": export_first["p95_ms"],
        "export_after_p50_ms": export_after["p50_ms"],
        "export_after_p95_ms": export_after["p95_ms"],
    }


async def _run(args: argparse.Namespace) -> dict:
    async with SessionLocal() as db:
        db_name = (await db.execute(text("SELECT current_database()"))).scalar_one()
        if not db_name.endswith("_bench") and not args.allow_non_bench:
            raise SystemExit(
                f"Từ chối chạy trên database {db_name!r}; "
                "dùng --allow-non-bench nếu thật sự cần"
            )
        enrollment_id, slide_id, lesson_id = await _fixture(db)
        visit_id, view_ids = await _seed(
            db,
            enrollment_id,
            slide_id,
            lesson_id,
            samples=args.samples,
            views=args.views,
        )

        timer = _SqlTimer()
        event.listen(engine.sync_engine, "before_cursor_execute", timer.before)
        event.listen(engine.sync_engine, "after_cursor_execute", timer.after)
        rss_before = _rss_mib()
        try:
            started = time.perf_counter()
            lines, size = await _consume(export_visit_lines(visit_id))
            total_ms = (time.perf_counter() - started) * 1000
            single = {
                "lines": lines,
                "bytes": size,
                "wall_ms": round(total_ms, 1),
                "pages": len(timer.page_times),
                "page_p50_ms": _percentile(timer.page_times, 50),
                "page_p95_ms": _percentile(timer.page_times, 95),
                "peak_rss_mib": round(
                    resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1
                ),
                "rss_delta_mib": round(_rss_mib() - rss_before, 1),
            }

            idle_result: dict = {}
            stop = asyncio.Event()
            poller = asyncio.create_task(
                _poll_idle_in_transaction(stop, idle_result)
            )
            pages_before = len(timer.page_times)
            started = time.perf_counter()
            concurrent = await asyncio.gather(
                *(
                    _consume(export_visit_lines(visit_id))
                    for _ in range(max(1, args.concurrency))
                )
            )
            concurrent_ms = (time.perf_counter() - started) * 1000
            concurrent_pages = timer.page_times[pages_before:]
            stop.set()
            await poller
            concurrent_result = {
                "exports": len(concurrent),
                "wall_ms": round(concurrent_ms, 1),
                "min_lines": min(item[0] for item in concurrent),
                "min_bytes": min(item[1] for item in concurrent),
                "page_p50_ms": _percentile(concurrent_pages, 50),
                "page_p95_ms": _percentile(concurrent_pages, 95),
                **idle_result,
            }
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", timer.before)
            event.remove(engine.sync_engine, "after_cursor_execute", timer.after)

        cursor = await _sample_cursor(db, view_ids, args.samples // 2)
        page = await _gaze_page(db, view_ids, cursor, limit=args.page_limit)
        legacy = await _legacy_pages(
            db,
            visit_id,
            cursor,
            samples=args.samples,
            limit=args.page_limit,
        )
        export_plan = "\n".join(
            (
                await db.execute(
                    text("EXPLAIN (ANALYZE, BUFFERS) " + VISIT_SAMPLE_SQL),
                    {"view_id": view_ids[0], "page_size": args.page_limit},
                )
            ).scalars()
        )

        if not args.keep:
            await db.rollback()
            await db.execute(
                text("DELETE FROM course_visits WHERE id = :id"),
                {"id": visit_id},
            )
            await db.commit()

        return {
            "database": db_name,
            "samples": args.samples,
            "views": len(view_ids),
            "single_export": single,
            "concurrent_export": concurrent_result,
            "gaze_page": page,
            "legacy": legacy,
            "export_page_seq_scan": "Seq Scan on gaze_samples" in export_plan,
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
