#!/usr/bin/env python3
"""Đo analyze_content_view trên một view tổng hợp (gate Phase 5).

Chạy trong image backend của stack benchmark:

    docker compose -p eyelearning-bench --env-file .env \
      -f docker-compose.yml -f benchmarks/stack/docker-compose.bench.yml \
      exec -T backend python /bench/backend/analysis_probe.py \
      --samples 54000 --chunk-size 3000 \
      --out /bench/baseline/<run-id>/backend/analysis_probe.json

Script chỉ tạo/xoá dữ liệu tạm trong database `*_bench`; không dùng cho dev
hoặc production.
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

# Khi chạy `python /bench/backend/analysis_probe.py`, sys.path chỉ có thư mục
# script; app nằm ở /app trong image backend.
if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from sqlalchemy import event, text  # noqa: E402

from app.db.session import SessionLocal, engine  # noqa: E402
from app.services import metrics  # noqa: E402


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=54_000)
    parser.add_argument("--chunk-size", type=int, default=metrics.SAMPLE_CHUNK_SIZE)
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


async def _seed(db, enrollment_id: str, slide_id: str, samples: int) -> tuple[str, str]:
    session_id = str(uuid.uuid4())
    view_id = str(uuid.uuid4())
    layout_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await db.execute(
        text(
            "INSERT INTO learning_sessions "
            "(id, enrollment_id, lesson_id, status, started_at, expires_at) "
            "SELECT CAST(:id AS uuid), CAST(:enrollment AS uuid), lesson_id, "
            "       'in_progress', CAST(:now AS timestamptz), "
            "       CAST(:expires AS timestamptz) "
            "FROM slides WHERE id = CAST(:slide AS uuid)"
        ),
        {
            "id": session_id,
            "enrollment": enrollment_id,
            "slide": slide_id,
            "now": now,
            "expires": now + timedelta(hours=1),
        },
    )
    await db.execute(
        text(
            "INSERT INTO content_views "
            "(id, session_id, slide_id, surface, sequence_no, started_at) "
            "VALUES (CAST(:id AS uuid), CAST(:session AS uuid), "
            "        CAST(:slide AS uuid), 'lesson', 0, "
            "        CAST(:now AS timestamptz))"
        ),
        {"id": view_id, "session": session_id, "slide": slide_id, "now": now},
    )
    await db.execute(
        text(
            "INSERT INTO view_layouts "
            "(id, content_view_id, layout_no, slide_rect, elements, captured_at) "
            "VALUES (CAST(:id AS uuid), CAST(:view AS uuid), 0, "
            "CAST(:rect AS JSONB), '[]'::jsonb, CAST(:now AS timestamptz))"
        ),
        {
            "id": layout_id,
            "view": view_id,
            "rect": json.dumps(
                {"left": 0.1, "top": 0.1, "width": 0.8, "height": 0.8}
            ),
            "now": now,
        },
    )
    await db.execute(
        text(
            "INSERT INTO gaze_samples "
            "(content_view_id, layout_id, client_batch_id, sequence, event_time, "
            " viewport_x, viewport_y, status, quality_flags) "
            "SELECT CAST(:view AS uuid), CAST(:layout AS uuid), "
            "       CAST(:batch AS uuid), g, "
            "       CAST(:base AS timestamptz) + "
            "       make_interval(secs => CAST(g * 0.066 AS double precision)), "
            "       CAST(0.2 + (g % 50) / 100.0 AS real), "
            "       CAST(0.2 + (g % 37) / 100.0 AS real), "
            "       'ok', '{}'::jsonb "
            "FROM generate_series(0, CAST(:count AS integer) - 1) AS g"
        ),
        {
            "view": view_id,
            "layout": layout_id,
            "batch": str(uuid.uuid4()),
            "base": now,
            "count": samples,
        },
    )
    await db.commit()
    return session_id, view_id


async def _run(args: argparse.Namespace) -> dict:
    async with SessionLocal() as db:
        db_name = (await db.execute(text("SELECT current_database()"))).scalar_one()
        if not db_name.endswith("_bench") and not args.allow_non_bench:
            raise SystemExit(
                f"Từ chối chạy trên database {db_name!r}; dùng --allow-non-bench nếu thật sự cần"
            )

        enrollment_id, slide_id, _lesson_id = await _fixture(db)
        session_id, view_id = await _seed(db, enrollment_id, slide_id, args.samples)

        txn_start: dict[int, float] = {}
        txn_times: list[float] = []
        update_times: list[float] = []
        stmt_start: dict[int, float] = {}

        def on_begin(conn) -> None:
            txn_start[id(conn)] = time.perf_counter()

        def on_commit(conn) -> None:
            started = txn_start.pop(id(conn), None)
            if started is not None:
                txn_times.append((time.perf_counter() - started) * 1000)

        def on_rollback(conn) -> None:
            txn_start.pop(id(conn), None)

        def before_execute(conn, cursor, statement, parameters, context, executemany):
            stmt_start[id(conn)] = time.perf_counter()

        def after_execute(conn, cursor, statement, parameters, context, executemany):
            started = stmt_start.pop(id(conn), None)
            if started is None:
                return
            normalized = statement.lstrip().upper()
            if normalized.startswith("UPDATE GAZE_SAMPLES"):
                update_times.append((time.perf_counter() - started) * 1000)

        event.listen(engine.sync_engine, "begin", on_begin)
        event.listen(engine.sync_engine, "commit", on_commit)
        event.listen(engine.sync_engine, "rollback", on_rollback)
        event.listen(engine.sync_engine, "before_cursor_execute", before_execute)
        event.listen(engine.sync_engine, "after_cursor_execute", after_execute)

        metrics.SAMPLE_CHUNK_SIZE = args.chunk_size
        try:
            started = time.perf_counter()
            view = await metrics.analyze_content_view(db, view_id)
            wall_ms = (time.perf_counter() - started) * 1000
            labels = (
                await db.execute(
                    text(
                        "SELECT count(*) FILTER (WHERE aoi_label IS NOT NULL), "
                        "       md5(string_agg(coalesce(aoi_label, ''), '|' "
                        "                     ORDER BY id)) "
                        "FROM gaze_samples WHERE content_view_id = :id"
                    ),
                    {"id": view_id},
                )
            ).one()
            result = {
                "database": db_name,
                "samples": args.samples,
                "chunk_size": args.chunk_size,
                "wall_ms": round(wall_ms, 1),
                "max_txn_ms": round(max(txn_times, default=0.0), 1),
                "max_chunk_update_ms": round(max(update_times, default=0.0), 1),
                "peak_rss_mib": round(
                    resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1
                ),
                "gaze_count": view.gaze_count,
                "on_slide_gaze_count": view.on_slide_gaze_count,
                "tracked_duration_ms": view.tracked_duration_ms,
                "fixation_count": view.fixation_count,
                "heatmap_sum": sum(sum(row) for row in view.heatmap_grid),
                "aoi_stats_count": len(view.aoi_stats),
                "labelled_samples": labels[0],
                "labels_checksum": labels[1],
                "analysis_status": view.analysis_status,
                "analysis_version": view.analysis_version,
            }
        finally:
            event.remove(engine.sync_engine, "begin", on_begin)
            event.remove(engine.sync_engine, "commit", on_commit)
            event.remove(engine.sync_engine, "rollback", on_rollback)
            event.remove(engine.sync_engine, "before_cursor_execute", before_execute)
            event.remove(engine.sync_engine, "after_cursor_execute", after_execute)
            if not args.keep:
                await db.rollback()
                await db.execute(
                    text("DELETE FROM content_views WHERE id = :id"),
                    {"id": view_id},
                )
                await db.execute(
                    text("DELETE FROM learning_sessions WHERE id = :id"),
                    {"id": session_id},
                )
                await db.commit()

        return result


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
