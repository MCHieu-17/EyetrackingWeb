#!/usr/bin/env python3
"""Đo recall/MRR của dense ANN so với exact scan trên câu hỏi course_qa.

Chạy trong image chatbot:
    python /bench/chatbot/retrieval_probe.py \
      --course-id <uuid> \
      --questions /bench/fixtures/chat_questions.template.jsonl \
      --out /bench/.../chatbot/retrieval.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, "/app")

from pgvector import Vector

from app.db import get_pool
from app.workflow.providers import get_embedding
from app.workflow.retrieval import DENSE_SQL, Retriever, rrf_fuse


def summarize(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "p50": None, "p95": None, "mean": None}
    ordered = sorted(values)
    return {
        "count": len(values),
        "p50": round(ordered[len(ordered) // 2], 2),
        "p95": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))], 2),
        "mean": round(statistics.mean(values), 2),
    }


def load_questions(path: Path, limit: int) -> list[str]:
    questions: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        if item.get("kind") != "course_qa":
            continue
        questions.append(item["question"])
        if limit and len(questions) >= limit:
            break
    return questions


def exact_dense(conn, retriever: Retriever, vector, lesson_ids, limit: int) -> list[dict]:
    with conn.transaction():
        conn.execute("SET LOCAL enable_indexscan = off")
        conn.execute("SET LOCAL enable_bitmapscan = off")
        return retriever._dense_rows(conn, vector, lesson_ids, limit)


def ann_dense(conn, retriever: Retriever, vector, lesson_ids, limit: int) -> list[dict]:
    with conn.transaction():
        retriever._apply_retrieval_settings(conn)
        return retriever._dense_rows(conn, vector, lesson_ids, limit)


def explain_plan(conn, retriever: Retriever, vector, lesson_ids, limit: int) -> str:
    with conn.transaction():
        retriever._apply_retrieval_settings(conn)
        rows = conn.execute(
            "EXPLAIN (ANALYZE, BUFFERS, COSTS OFF) " + DENSE_SQL,
            (vector, lesson_ids, vector, limit),
        ).fetchall()
    lines = [str(next(iter(row.values()))) for row in rows]
    return "\n".join(line[:240] for line in lines[:80])


def rank_of(doc_id, docs: list[dict]) -> int:
    for index, doc in enumerate(docs, start=1):
        if str(doc["id"]) == str(doc_id):
            return index
    return 0


async def main_async(args) -> dict:
    questions = load_questions(Path(args.questions), args.limit)
    if not questions:
        raise SystemExit("Không có câu hỏi course_qa")

    retriever = Retriever()
    embedding = get_embedding()
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    exact_ms: list[float] = []
    ann_ms: list[float] = []
    per_question: list[dict] = []
    plan = ""

    with get_pool().connection() as conn:
        lesson_ids = retriever._course_lesson_ids(conn, args.course_id)
        if not lesson_ids:
            raise SystemExit(f"Course {args.course_id} không có slide ready/published")

        for question in questions:
            vector = Vector(await embedding.aembed_query(question))
            bm25 = retriever._bm25_rows(conn, question, lesson_ids)

            started = time.perf_counter()
            exact = exact_dense(
                conn, retriever, vector, lesson_ids, retriever.dense_candidates
            )
            exact_ms.append((time.perf_counter() - started) * 1000)

            started = time.perf_counter()
            ann = ann_dense(
                conn, retriever, vector, lesson_ids, retriever.dense_candidates
            )
            ann_ms.append((time.perf_counter() - started) * 1000)

            exact_docs = rrf_fuse(
                [(bm25, 1.0), (exact, 1.0)], retriever.rrf_k, retriever.top_k
            )
            ann_docs = rrf_fuse(
                [(bm25, 1.0), (ann, 1.0)], retriever.rrf_k, retriever.top_k
            )

            expected = {str(doc["id"]) for doc in exact_docs}
            got = {str(doc["id"]) for doc in ann_docs}
            recall = len(expected & got) / len(expected) if expected else 1.0
            recalls.append(recall)
            first_rank = rank_of(exact_docs[0]["id"], ann_docs) if exact_docs else 1
            reciprocal_ranks.append(1.0 / first_rank if first_rank else 0.0)

            if not plan:
                plan = explain_plan(
                    conn, retriever, vector, lesson_ids, retriever.dense_candidates
                )

            per_question.append(
                {
                    "question": question,
                    "recall": round(recall, 4),
                    "first_rank": first_rank,
                    "exact_count": len(exact_docs),
                    "ann_count": len(ann_docs),
                }
            )

    retriever.close()
    return {
        "course_id": args.course_id,
        "questions": len(questions),
        "top_k": retriever.top_k,
        "dense_candidates": retriever.dense_candidates,
        "ef_search": retriever.ef_search,
        "recall_at_k": round(statistics.mean(recalls), 4),
        "mrr": round(statistics.mean(reciprocal_ranks), 4),
        "exact_dense_ms": summarize(exact_ms),
        "ann_dense_ms": summarize(ann_ms),
        "plan_uses_hnsw": "idx_slides_hnsw" in plan,
        "plan": plan,
        "per_question": per_question,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--course-id", required=True)
    parser.add_argument("--questions", required=True)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    result = asyncio.run(main_async(args))
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
