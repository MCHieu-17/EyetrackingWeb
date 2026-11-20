#!/usr/bin/env python3
"""Đo ingest 1 lesson theo từng pha: render PDF, VLM, embedding, DB.

Chạy trong image chatbot:
    docker compose ... exec -T chatbot \
      python /bench/chatbot/ingest_probe.py \
      --lesson-id <uuid> --limit 4 \
      --out /bench/.../chatbot/ingest.json

Script monkeypatch timer quanh method của Ingestion; không sửa code service.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, "/app")

from app.db import get_pool
from app.services.ingest import Ingestion


def pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(len(ordered) * q))], 2)


def summarize(values: list[float]) -> dict:
    return {
        "count": len(values),
        "p50": pct(values, 0.50),
        "p95": pct(values, 0.95),
        "p99": pct(values, 0.99),
        "mean": round(statistics.mean(values), 2) if values else None,
        "max": round(max(values), 2) if values else None,
    }


def lesson_slide_ids(lesson_id: str, limit: int | None) -> list[str]:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM slides WHERE lesson_id = %s::uuid ORDER BY position LIMIT %s",
                (lesson_id, limit or 10000),
            )
            return [str(row["id"]) for row in cur.fetchall()]


def reset_slides(slide_ids: list[str]) -> None:
    if not slide_ids:
        return
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE slides SET index_status='pending', index_error=NULL, "
                "transcript='', embedding=NULL WHERE id = ANY(%s::uuid[])",
                (slide_ids,),
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lesson-id", required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    slide_ids = lesson_slide_ids(args.lesson_id, args.limit or None)
    if not slide_ids:
        raise SystemExit("Lesson không có slide")
    reset_slides(slide_ids)

    ingestion = Ingestion()
    local = threading.local()
    records: list[dict] = []
    lock = threading.Lock()

    def rec(slide_id: str) -> dict:
        item = getattr(local, "item", None)
        if item is None or item["slide_id"] != slide_id:
            item = {"slide_id": slide_id}
            local.item = item
            with lock:
                records.append(item)
        return item

    def timed(attr: str, slide_arg=None):
        original = getattr(ingestion, attr)

        def wrapper(*a, **kw):
            slide = slide_arg(a, kw) if slide_arg else None
            item = rec(str(slide.get("slide_id"))) if slide else getattr(local, "item", None)
            started = time.perf_counter()
            try:
                return original(*a, **kw)
            finally:
                if item is not None:
                    item[f"{attr}_ms"] = round((time.perf_counter() - started) * 1000, 2)

        setattr(ingestion, attr, wrapper)

    timed("_load_image", lambda a, kw: a[0])
    timed("_describe_image", None)
    timed("_upsert", lambda a, kw: a[0])
    timed("_mark", lambda a, kw: {"slide_id": a[0]})

    original_embed = ingestion.embedding.embed_documents

    def embed_wrapper(texts):
        started = time.perf_counter()
        try:
            return original_embed(texts)
        finally:
            elapsed = round((time.perf_counter() - started) * 1000, 2)
            current = getattr(local, "item", None)
            if current is not None:
                current["embedding_ms"] = elapsed

    ingestion.embedding.embed_documents = embed_wrapper

    started = time.perf_counter()
    processed, failed, errors = ingestion.embed_slides(slide_ids)
    wall_ms = round((time.perf_counter() - started) * 1000, 2)

    for item in records:
        item["total_ms"] = round(
            sum(
                float(item.get(k, 0) or 0)
                for k in (
                    "_load_image_ms",
                    "_describe_image_ms",
                    "embedding_ms",
                    "_upsert_ms",
                    "_mark_ms",
                )
            ),
            2,
        )

    payload = {
        "lesson_id": args.lesson_id,
        "slide_count": len(slide_ids),
        "processed": processed,
        "failed": failed,
        "errors": errors,
        "wall_ms": wall_ms,
        "slides_per_second": round(len(slide_ids) / (wall_ms / 1000), 3) if wall_ms else None,
        "stages_ms": {
            "pdf_render": summarize(
                [float(r["_load_image_ms"]) for r in records if "_load_image_ms" in r]
            ),
            "vlm": summarize(
                [float(r["_describe_image_ms"]) for r in records if "_describe_image_ms" in r]
            ),
            "embedding": summarize(
                [float(r["embedding_ms"]) for r in records if "embedding_ms" in r]
            ),
            "db_upsert": summarize([float(r["_upsert_ms"]) for r in records if "_upsert_ms" in r]),
            "db_mark": summarize([float(r["_mark_ms"]) for r in records if "_mark_ms" in r]),
        },
        "slides": records,
    }
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: payload[k] for k in ("processed", "failed", "wall_ms", "stages_ms")}, indent=2
        )
    )
    ingestion.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
