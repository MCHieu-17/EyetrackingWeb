#!/usr/bin/env python3
"""Tổng hợp artifact của một run thành summary.json/summary.md."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def metric_values(data: dict, name: str) -> dict:
    metric = (data.get("metrics") or {}).get(name) or {}
    return metric.get("values") or {}


def collect_k6(run: Path) -> list[dict]:
    out = []
    for path in sorted((run / "backend/k6").glob("*.summary.json")):
        if path.name.startswith("test-") or path.name.startswith("qcount-"):
            continue
        data = read_json(path)
        if not data:
            continue
        duration = metric_values(data, "http_req_duration")
        failed = metric_values(data, "http_req_failed")
        reqs = metric_values(data, "http_reqs")
        out.append(
            {
                "file": path.name,
                "scenario": path.stem.replace(".summary", ""),
                "p50": duration.get("p(50)") or duration.get("med"),
                "p95": duration.get("p(95)"),
                "p99": duration.get("p(99)"),
                "avg": duration.get("avg"),
                "rps": reqs.get("rate"),
                "error_rate": failed.get("rate"),
                "count": reqs.get("count"),
            }
        )
    return out


def collect_query_counts(run: Path) -> dict:
    import csv

    out = {}
    for path in sorted((run / "backend/pg_stat_statements").glob("query-*_top_queries.csv")):
        name = path.name.removeprefix("query-").removesuffix("_top_queries.csv")
        try:
            with path.open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            calls = sum(int(float(row.get("calls") or 0)) for row in rows)
            out[name] = {
                "queries_total": calls,
                "iterations": 20,
                "queries_per_request": round(calls / 20, 2),
            }
        except Exception:
            continue
    return out


def collect_gaze(run: Path) -> dict:
    stage = read_json(run / "gaze/stage-latency.json") or {}
    ws = read_json(run / "gaze/ws-load.json") or {}
    stages = {}
    for image, data in (stage.get("images") or {}).items():
        stages[image] = (data.get("stages_ms") or {}).get("total")
    return {
        "device": stage.get("device"),
        "precision": stage.get("precision"),
        "model": stage.get("model"),
        "vram_allocated_mib": stage.get("cuda_max_memory_allocated_mib"),
        "rss_kib": stage.get("max_rss_kib"),
        "stage_total": stages,
        "ws": ws.get("scenarios") or [],
    }


def collect_chatbot(run: Path) -> dict:
    def q(name: str):
        data = read_json(run / f"chatbot/{name}.json") or {}
        return data.get("results") or []

    return {
        "query_chatbot": q("query-chatbot"),
        "query_backend": q("query-backend"),
        "components": read_json(run / "chatbot/components.json") or {},
        "components_all": read_json(run / "chatbot/components-all.json") or {},
        "ingest": read_json(run / "chatbot/ingest.json") or {},
    }


def collect_frontend(run: Path) -> dict:
    return {
        "bundle": read_json(run / "frontend/bundle-size.json") or {},
        "lighthouse": read_json(run / "frontend/lighthouse-summary.json") or {},
    }


def collect_auth(run: Path) -> dict:
    return read_json(run / "backend/auth_probe.json") or {}


def collect_redis(run: Path) -> dict:
    base = run / "backend/redis"
    return {
        "before": read_json(base / "before_summary.json") or {},
        "after": read_json(base / "after_summary.json") or {},
    }


def md_table(rows: list[dict], columns: list[str]) -> list[str]:
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join(["---"] * len(columns)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(c, "")) for c in columns) + " |")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--out", default="")
    parser.add_argument("--md", default="")
    args = parser.parse_args()
    run = Path(args.run_dir).resolve()
    out = Path(args.out or run / "summary.json")
    md = Path(args.md or run / "summary.md")

    fixtures = read_json(run / "fixtures.json") or {}
    summary = {
        "run": run.name,
        "fixtures": {
            "scale": fixtures.get("scale"),
            "counts": fixtures.get("counts"),
            "pdf_sha256": fixtures.get("pdf_sha256"),
        },
        "backend": {
            "k6": collect_k6(run),
            "query_counts": collect_query_counts(run),
            "auth": collect_auth(run),
        },
        "gaze": collect_gaze(run),
        "chatbot": collect_chatbot(run),
        "frontend": collect_frontend(run),
        "redis": collect_redis(run),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")

    lines = [f"# Benchmark summary — {run.name}", ""]
    counts = summary["fixtures"].get("counts") or {}
    if counts:
        lines += ["## Dataset", "", "| Table | Rows |", "|---|---:|"]
        for key, value in counts.items():
            lines.append(f"| {key} | {value:,} |")
        lines.append("")
    if summary["backend"]["k6"]:
        lines += ["## Backend (k6)", ""]
        lines += md_table(
            summary["backend"]["k6"],
            ["scenario", "p50", "p95", "p99", "rps", "error_rate", "count"],
        )
        lines.append("")
    if summary["backend"].get("query_counts"):
        lines += ["### Queries mỗi request", ""]
        lines += md_table(
            [{"endpoint": k, **v} for k, v in summary["backend"]["query_counts"].items()],
            ["endpoint", "queries_total", "iterations", "queries_per_request"],
        )
        lines.append("")
    auth = summary["backend"].get("auth") or {}
    if auth:
        lines += [
            "### Auth memory-hit",
            "",
            f"- p50/p95/p99: {auth.get('p50_ms')} / {auth.get('p95_ms')} / "
            f"{auth.get('p99_ms')} ms",
            f"- Redis GET/call: {auth.get('redis_get_per_call')} "
            f"({auth.get('redis_get_calls')} / {auth.get('iterations')})",
            "",
        ]
    gaze = summary["gaze"]
    if gaze.get("stage_total"):
        lines += [
            "## Gaze",
            "",
            f"- device: `{gaze.get('device')}` / `{gaze.get('precision')}` / `{gaze.get('model')}`",
            "",
        ]
        lines += md_table(
            [{"image": k, **v} for k, v in gaze["stage_total"].items()],
            ["image", "count", "p50", "p95", "p99"],
        )
        lines.append("")
    ws = gaze.get("ws") or []
    if ws:
        lines += ["### Gaze WebSocket", ""]
        lines += md_table(
            [
                {
                    "sessions": s.get("sessions"),
                    "resp/s": s.get("responses_per_s"),
                    "fps/session": s.get("fps_per_session"),
                    "drop": s.get("drop_rate"),
                    "p95": (s.get("rtt_ms") or {}).get("p95"),
                    "p99": (s.get("rtt_ms") or {}).get("p99"),
                }
                for s in ws
            ],
            ["sessions", "resp/s", "fps/session", "drop", "p95", "p99"],
        )
        lines.append("")
    chat = summary["chatbot"]
    if chat["query_chatbot"]:
        lines += ["## Chatbot", "", "### Query trực tiếp", ""]
        lines += md_table(
            [
                {
                    "concurrency": r.get("concurrency"),
                    "rps": r.get("rps"),
                    "ttft_p95": (r.get("ttft_total_ms") or {}).get("p95"),
                    "total_p95": (r.get("t_total_ms") or {}).get("p95"),
                    "error": r.get("error_rate"),
                }
                for r in chat["query_chatbot"]
            ],
            ["concurrency", "rps", "ttft_p95", "total_p95", "error"],
        )
        lines.append("")
    ingest = chat.get("ingest") or {}
    if ingest:
        lines += [
            "### Ingest",
            "",
            f"- slides: {ingest.get('slide_count')} / processed: {ingest.get('processed')} / wall: {ingest.get('wall_ms')} ms",
            "",
        ]
        lines += md_table(
            [{"stage": k, **(v or {})} for k, v in (ingest.get("stages_ms") or {}).items()],
            ["stage", "p50", "p95", "mean"],
        )
        lines.append("")
    bundle = (summary["frontend"].get("bundle") or {}).get("static")
    if bundle:
        lines += [
            "## Frontend",
            "",
            f"- static raw: {bundle.get('raw')} bytes / gzip: {bundle.get('gzip')} bytes",
            "",
        ]
    lh = summary["frontend"].get("lighthouse") or {}
    if lh:
        lines += ["### Lighthouse", ""]
        lines += md_table(
            [
                {
                    "page": v.get("page"),
                    "form": v.get("form"),
                    "score": v.get("score"),
                    "a11y": v.get("a11y"),
                    "best_practices": v.get("bestPractices"),
                    "lcp": v.get("lcp"),
                    "tbt": v.get("tbt"),
                    "ttfb": v.get("ttfb"),
                }
                for v in lh.values()
            ],
            ["page", "form", "score", "a11y", "best_practices", "lcp", "tbt", "ttfb"],
        )
        lines.append("")
    redis_before = summary["redis"].get("before") or {}
    redis_after = summary["redis"].get("after") or {}
    if redis_before or redis_after:
        lines += [
            "## Redis",
            "",
            f"- hit rate before: {redis_before.get('hit_rate')}",
            f"- hit rate after: {redis_after.get('hit_rate')}",
            "",
        ]

    md.write_text("\n".join(lines).rstrip() + "\n")
    print(json.dumps({"summary": str(out), "markdown": str(md)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
