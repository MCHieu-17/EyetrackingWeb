#!/usr/bin/env python3
"""Đo TTFT/tổng thời gian chatbot qua SSE, tách stage theo event.

Chạy trong image chatbot:
    docker compose ... exec -T chatbot \
      python /bench/chatbot/query_probe.py \
      --url http://127.0.0.1:8000 --mode chatbot \
      --fixtures /bench/.../fixtures.json \
      --questions /bench/fixtures/chat_questions.template.jsonl \
      --out /bench/.../chatbot/query.json

Backend mode:
      --mode backend --url http://backend:8001
      --token-file /bench/.../.runtime/tokens.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import time
from pathlib import Path

import httpx


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


def load_questions(path: Path, fixtures: dict) -> list[dict]:
    ids = fixtures["ids"]
    replacements = {
        "__COURSE_ID__": ids["core_course_id"],
        "__LESSON_ID__": ids["core_lesson_ids"][0],
        "__MODULE_TITLE__": "Benchmark Module",
        "__LESSON_TITLE__": "Benchmark Lesson",
    }
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        for key, value in replacements.items():
            item["question"] = item["question"].replace(key, value)
        out.append(item)
    return out


def payload_for(item: dict, fixtures: dict, index: int) -> dict:
    ids = fixtures["ids"]
    contexts = fixtures.get("chat_contexts") or []
    ctx = contexts[index % len(contexts)] if contexts else {}
    return {
        "message": item["question"],
        "course_id": ids["core_course_id"],
        "thread_id": ctx.get("id", f"00000000-0000-4000-8000-{index:012d}"),
        "context_key": ctx.get("context_key", ""),
        "history": item.get("history") or [],
        "lesson_id": ids["core_lesson_ids"][index % len(ids["core_lesson_ids"])],
        "lesson_title": "Benchmark Lesson",
        "module_title": "Benchmark Module",
        "assignment_id": None,
        "attempt_id": None,
        "assignment_title": "",
        "assignment_context": "",
        "support_mode": "hint",
    }


async def one_request(
    client: httpx.AsyncClient,
    *,
    url: str,
    mode: str,
    token: str,
    item: dict,
    fixtures: dict,
    index: int,
) -> dict:
    started = time.perf_counter()
    marks: dict[str, float] = {}
    first_token: float | None = None
    status_code = None
    error = None
    answer_parts: list[str] = []
    done_payload = None

    request_token = token[index % len(token)] if isinstance(token, list) else token
    if mode == "backend":
        path = f"/api/courses/{fixtures['ids']['core_course_id']}/chat/stream"
        body = {
            "message": item["question"],
            "lesson_id": fixtures["ids"]["core_lesson_ids"][
                index % len(fixtures["ids"]["core_lesson_ids"])
            ],
        }
        headers = {"Authorization": f"Bearer {request_token}"}
    else:
        path = "/chat/stream"
        body = payload_for(item, fixtures, index)
        headers = {"X-Chatbot-Token": request_token}

    try:
        async with client.stream(
            "POST", f"{url.rstrip('/')}{path}", json=body, headers=headers
        ) as response:
            status_code = response.status_code
            if response.status_code >= 400:
                text = (await response.aread()).decode("utf-8", errors="replace")[:500]
                return {
                    "id": item.get("id"),
                    "kind": item.get("kind"),
                    "status_code": status_code,
                    "error": text,
                    "total_ms": round((time.perf_counter() - started) * 1000, 2),
                }
            event = ""
            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    event = line.split(":", 1)[1].strip()
                    continue
                if not line.startswith("data:"):
                    continue
                raw = line.split(":", 1)[1].strip()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                now = time.perf_counter()
                if event == "status":
                    stage = str((data or {}).get("stage", ""))
                    if stage and stage not in marks:
                        marks[stage] = now
                elif event == "citations":
                    marks.setdefault("citations", now)
                elif event == "token":
                    if first_token is None:
                        first_token = now
                    answer_parts.append(str((data or {}).get("text", "")))
                elif event == "done":
                    done_payload = data
                    marks.setdefault("done", now)
                elif event == "error":
                    error = str((data or {}).get("message", "error"))
            marks.setdefault("eof", time.perf_counter())
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"

    def ms(mark: str) -> float | None:
        value = marks.get(mark)
        return round((value - started) * 1000, 2) if value is not None else None

    result = {
        "id": item.get("id"),
        "kind": item.get("kind"),
        "status_code": status_code,
        "error": error,
        "ttft_total_ms": round((first_token - started) * 1000, 2) if first_token else None,
        "t_prep_ms": ms("retrieving"),
        "t_retrieve_ms": (
            round((marks["citations"] - marks["retrieving"]) * 1000, 2)
            if "retrieving" in marks and "citations" in marks
            else None
        ),
        "t_llm_ttft_ms": (
            round((first_token - marks["generating"]) * 1000, 2)
            if first_token and "generating" in marks
            else None
        ),
        "t_total_ms": ms("done"),
        "t_conn_close_ms": ms("eof"),
        "answer_chars": len("".join(answer_parts)),
        "finish_reason": (done_payload or {}).get("finish_reason"),
        "verified": (done_payload or {}).get("verified"),
        "intent": (done_payload or {}).get("intent"),
    }
    return result


def aggregate(records: list[dict], key: str) -> dict:
    values = [float(r[key]) for r in records if r.get(key) is not None and not r.get("error")]
    return summarize(values)


async def run_level(
    *,
    url: str,
    mode: str,
    token: str,
    items: list[dict],
    fixtures: dict,
    concurrency: int,
    repeats: int,
) -> dict:
    sem = asyncio.Semaphore(concurrency)
    limits = httpx.Limits(max_connections=max(20, concurrency * 2))
    async with httpx.AsyncClient(timeout=180, limits=limits) as client:

        async def worker(item: dict, index: int):
            async with sem:
                return await one_request(
                    client,
                    url=url,
                    mode=mode,
                    token=token,
                    item=item,
                    fixtures=fixtures,
                    index=index,
                )

        tasks = []
        for repeat in range(repeats):
            for index, item in enumerate(items):
                tasks.append(worker(item, index + repeat * len(items)))
        started = time.perf_counter()
        records = await asyncio.gather(*tasks)
        wall = time.perf_counter() - started

    errors = [r for r in records if r.get("error")]
    return {
        "concurrency": concurrency,
        "requests": len(records),
        "repeats": repeats,
        "wall_s": round(wall, 3),
        "rps": round(len(records) / wall, 3) if wall else None,
        "error_rate": round(len(errors) / len(records), 4) if records else None,
        "ttft_total_ms": aggregate(records, "ttft_total_ms"),
        "t_prep_ms": aggregate(records, "t_prep_ms"),
        "t_retrieve_ms": aggregate(records, "t_retrieve_ms"),
        "t_llm_ttft_ms": aggregate(records, "t_llm_ttft_ms"),
        "t_total_ms": aggregate(records, "t_total_ms"),
        "t_conn_close_ms": aggregate(records, "t_conn_close_ms"),
        "by_kind": {
            kind: {
                "ttft_total_ms": aggregate(
                    [r for r in records if r.get("kind") == kind], "ttft_total_ms"
                ),
                "t_total_ms": aggregate(
                    [r for r in records if r.get("kind") == kind], "t_total_ms"
                ),
            }
            for kind in sorted({str(r.get("kind")) for r in records})
        },
        "errors": errors[:10],
        "records_sample": records[:5],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--mode", choices=["chatbot", "backend"], default="chatbot")
    parser.add_argument("--token", default=os.environ.get("CHATBOT_INTERNAL_TOKEN", ""))
    parser.add_argument("--token-file", default="")
    parser.add_argument("--fixtures", required=True)
    parser.add_argument("--questions", required=True)
    parser.add_argument("--concurrency", default="1,5,10,20")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    fixtures = json.loads(Path(args.fixtures).read_text(encoding="utf-8"))
    items = load_questions(Path(args.questions), fixtures)
    if args.limit > 0:
        items = items[: args.limit]
    token = args.token
    if args.mode == "backend":
        if not args.token_file:
            raise SystemExit("backend mode cần --token-file")
        tokens = json.loads(Path(args.token_file).read_text(encoding="utf-8"))
        token = [item["token"] for item in tokens.get("students", [])]
        if not token:
            token = tokens["student"]["token"]
    if not token:
        raise SystemExit("Thiếu token")

    levels = [int(item) for item in args.concurrency.split(",") if item.strip()]
    results = []
    for level in levels:
        print(f"[chatbot] concurrency={level} repeats={args.repeats}")
        results.append(
            asyncio.run(
                run_level(
                    url=args.url,
                    mode=args.mode,
                    token=token,
                    items=items,
                    fixtures=fixtures,
                    concurrency=level,
                    repeats=args.repeats,
                )
            )
        )
    payload = {
        "url": args.url,
        "mode": args.mode,
        "question_count": len(items),
        "results": results,
    }
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            [
                {
                    "concurrency": r["concurrency"],
                    "rps": r["rps"],
                    "ttft": r["ttft_total_ms"],
                    "total": r["t_total_ms"],
                }
                for r in results
            ],
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
