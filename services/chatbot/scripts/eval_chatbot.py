#!/usr/bin/env python3
"""Đánh giá chatbot qua API /chat bằng bộ câu hỏi JSONL.

Chạy từ repo root:
    CHATBOT_INTERNAL_TOKEN=... python services/chatbot/scripts/eval_chatbot.py

Script gửi tuần tự từng câu, đo latency, kiểm tra citation và ghi kết quả
JSONL. Lỗi HTTP/timeout được ghi vào record `error` và không dừng cả bộ.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import httpx

DEFAULT_URL = "http://localhost:8002"
DEFAULT_INPUT = "services/chatbot/tests/eval/questions.example.jsonl"
DEFAULT_OUTPUT = "/tmp/chatbot-eval-results.jsonl"
DEFAULT_COURSE_ID = "00000000-0000-0000-0000-000000000000"
DEFAULT_THREAD_ID = "eval-thread"

_CITATION_RE = re.compile(r"\[(\d+)\]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Đánh giá chatbot qua API /chat bằng bộ câu hỏi JSONL."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"Base URL của chatbot service (mặc định: {DEFAULT_URL}).",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("CHATBOT_INTERNAL_TOKEN", ""),
        help="Token nội bộ, mặc định lấy từ env CHATBOT_INTERNAL_TOKEN.",
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT,
        help=f"File JSONL câu hỏi (mặc định: {DEFAULT_INPUT}).",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"File JSONL kết quả (mặc định: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Timeout mỗi request, tính bằng giây (mặc định: 120).",
    )
    return parser.parse_args()


def resolve_input(path_str: str) -> Path:
    """Trả về đường dẫn input; fallback theo vị trí script khi chạy trong service."""
    path = Path(path_str)
    if path.is_file():
        return path
    if path_str == DEFAULT_INPUT:
        fallback = Path(__file__).resolve().parents[1] / "tests/eval/questions.example.jsonl"
        if fallback.is_file():
            return fallback
    return path


def load_questions(path: Path) -> list[tuple[int, dict[str, Any]]]:
    """Đọc JSONL, bỏ qua dòng trống và dòng lỗi cú pháp."""
    items: list[tuple[int, dict[str, Any]]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_no, raw in enumerate(handle, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                item = json.loads(raw)
            except json.JSONDecodeError as exc:
                print(
                    f"[cảnh báo] dòng {line_no}: JSON không hợp lệ ({exc}); bỏ qua",
                    file=sys.stderr,
                )
                continue
            if not isinstance(item, dict):
                print(
                    f"[cảnh báo] dòng {line_no}: phải là JSON object; bỏ qua",
                    file=sys.stderr,
                )
                continue
            items.append((line_no, item))
    return items


def build_payload(item: dict[str, Any], question: str) -> dict[str, Any]:
    """Map field của input JSONL sang body ChatRequest."""
    return {
        "message": question,
        "course_id": item.get("course_id") or DEFAULT_COURSE_ID,
        "course_version_id": item.get("course_version_id"),
        "thread_id": item.get("thread_id") or DEFAULT_THREAD_ID,
        "context_key": item.get("context_key") or "",
        "history": item.get("history") or [],
        "lesson_id": item.get("lesson_id"),
        "lesson_version_id": item.get("lesson_version_id"),
        "lesson_title": item.get("lesson_title") or "",
        "module_title": item.get("module_title") or "",
        "attempt_id": item.get("attempt_id"),
        "assignment_id": item.get("assignment_id"),
        "assignment_title": item.get("assignment_title") or "",
        "assignment_context": item.get("assignment_context") or "",
        "support_mode": item.get("support_mode") or "hint",
    }


def extract_citation_ids(answer: str) -> list[int]:
    """Lấy các số citation dạng [n] trong câu trả lời, đã sắp xếp và khử trùng."""
    return sorted({int(match.group(1)) for match in _CITATION_RE.finditer(answer)})


def base_record(item: dict[str, Any], question: str) -> dict[str, Any]:
    record: dict[str, Any] = {}
    if "id" in item:
        record["id"] = item["id"]
    record["question"] = question
    return record


def success_record(
    item: dict[str, Any],
    question: str,
    data: dict[str, Any],
    latency_ms: float,
) -> dict[str, Any]:
    citations = data.get("citations")
    if not isinstance(citations, list):
        citations = []
    answer = data.get("answer")
    if not isinstance(answer, str):
        answer = ""

    citation_ids = extract_citation_ids(answer)
    citation_count = len(citations)
    intent = data.get("intent")
    # LMS và greeting/thanks không cần citation slide.
    citation_required = intent not in {"lms", "general"}
    citation_valid = (
        any(1 <= number <= citation_count for number in citation_ids)
        if citation_required
        else True
    )
    record = base_record(item, question)
    record.update(
        {
            "answer": answer,
            "citations": citations,
            "intent": intent,
            "verified": bool(data.get("verified", False)),
            "finish_reason": data.get("finish_reason") or "",
            "latency_ms": latency_ms,
            "citation_count": citation_count,
            "citation_required": citation_required,
            "citation_valid": citation_valid,
            "citation_ids": citation_ids,
        }
    )
    return record


def error_record(
    item: dict[str, Any],
    question: str,
    error: str,
    latency_ms: float,
    status_code: int | None = None,
) -> dict[str, Any]:
    record = base_record(item, question)
    record.update(
        {
            "error": error,
            "latency_ms": latency_ms,
            "answer": None,
            "citations": [],
            "intent": None,
            "verified": False,
            "finish_reason": "error",
            "citation_count": 0,
            "citation_required": True,
            "citation_valid": False,
            "citation_ids": [],
        }
    )
    if status_code is not None:
        record["status_code"] = status_code
    return record


def call_chat(
    client: httpx.Client,
    url: str,
    token: str,
    payload: dict[str, Any],
    timeout: float,
) -> tuple[dict[str, Any] | None, str | None, float, int | None]:
    """Gọi /chat, trả về (data, error, latency_ms, status_code)."""
    started = time.perf_counter()
    try:
        response = client.post(
            url,
            json=payload,
            headers={"X-Chatbot-Token": token},
        )
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        if response.status_code >= 400:
            detail = response.text.strip().replace("\n", " ")
            if len(detail) > 500:
                detail = detail[:500] + "..."
            return None, f"HTTP {response.status_code}: {detail}", latency_ms, response.status_code
        try:
            data = response.json()
        except ValueError:
            return None, "Response không phải JSON hợp lệ", latency_ms, response.status_code
        if not isinstance(data, dict):
            return None, "Response JSON không phải object", latency_ms, response.status_code
        return data, None, latency_ms, response.status_code
    except httpx.TimeoutException as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        return None, f"Timeout sau {timeout:g}s: {exc}", latency_ms, None
    except httpx.HTTPError as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        return None, f"Lỗi HTTP: {exc}", latency_ms, None


def percentile(values: list[float], p: float) -> float:
    """Percentile nội suy tuyến tính, không cần dependency ngoài."""
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * p / 100
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def print_summary(records: list[dict[str, Any]]) -> None:
    total = len(records)
    print("\n=== Tóm tắt đánh giá chatbot ===")
    if total == 0:
        print("Không có câu hỏi nào được xử lý.")
        return

    errors = sum(1 for record in records if record.get("error"))
    latencies = [
        float(record["latency_ms"])
        for record in records
        if not record.get("error") and "latency_ms" in record
    ]
    citation_required = [
        record for record in records if record.get("citation_required", True)
    ]
    citation_valid = sum(
        1 for record in citation_required if record.get("citation_valid")
    )
    verified = sum(1 for record in records if record.get("verified"))
    finish_reasons = Counter(str(record.get("finish_reason") or "unknown") for record in records)

    print(f"Tổng số câu: {total} (lỗi: {errors})")
    if latencies:
        print(
            "Latency câu thành công: "
            f"p50={percentile(latencies, 50):.1f} ms, "
            f"p95={percentile(latencies, 95):.1f} ms"
        )
    else:
        print("Latency câu thành công: không có dữ liệu")
    if citation_required:
        print(
            f"citation_valid: {citation_valid}/{len(citation_required)} "
            f"({citation_valid / len(citation_required) * 100:.1f}%) "
            f"trên {len(citation_required)} câu cần citation"
        )
    else:
        print("citation_valid: không có câu nào cần citation")
    print(f"verified: {verified}/{total} ({verified / total * 100:.1f}%)")
    print("finish_reason:")
    for reason, count in finish_reasons.most_common():
        print(f"  {reason}: {count} ({count / total * 100:.1f}%)")


def main() -> int:
    args = parse_args()
    token = (args.token or os.getenv("CHATBOT_INTERNAL_TOKEN", "")).strip()
    if not token:
        print(
            "Lỗi: thiếu token. Truyền --token hoặc đặt env CHATBOT_INTERNAL_TOKEN.",
            file=sys.stderr,
        )
        return 2

    input_path = resolve_input(args.input)
    if not input_path.is_file():
        print(f"Lỗi: không tìm thấy file input: {input_path}", file=sys.stderr)
        return 2

    items = load_questions(input_path)
    if not items:
        print(f"Lỗi: không có câu hỏi hợp lệ trong {input_path}", file=sys.stderr)
        return 2

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    chat_url = args.url.rstrip("/")
    if not chat_url.endswith("/chat"):
        chat_url += "/chat"

    records: list[dict[str, Any]] = []
    with (
        httpx.Client(timeout=args.timeout) as client,
        output_path.open("w", encoding="utf-8") as output,
    ):
        for index, (line_no, item) in enumerate(items, 1):
            raw_question = item.get("question")
            if not isinstance(raw_question, str) or not raw_question.strip():
                record = error_record(
                    item,
                    "",
                    "Thiếu field 'question' hoặc rỗng",
                    0.0,
                )
                records.append(record)
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
                output.flush()
                print(
                    f"[{index}/{len(items)}] dòng {line_no}: thiếu question",
                    file=sys.stderr,
                )
                continue

            question = raw_question.strip()
            payload = build_payload(item, question)
            data, error, latency_ms, status_code = call_chat(
                client, chat_url, token, payload, args.timeout
            )

            if error is not None:
                record = error_record(item, question, error, latency_ms, status_code)
                print(
                    f"[{index}/{len(items)}] {question[:60]} -> lỗi: {error}",
                    file=sys.stderr,
                )
            else:
                assert data is not None
                record = success_record(item, question, data, latency_ms)
                print(
                    f"[{index}/{len(items)}] {question[:60]} -> {latency_ms:.0f} ms",
                    file=sys.stderr,
                )

            records.append(record)
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
            output.flush()

    print_summary(records)
    print(f"\nĐã ghi {len(records)} record vào {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
