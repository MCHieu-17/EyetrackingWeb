#!/usr/bin/env python3
"""Đo component chatbot: retriever, LLM, embedding, VLM.

Chạy trong image chatbot:
    docker compose ... exec -T chatbot \
      python /bench/chatbot/component_bench.py --mode retriever \
      --course-id <uuid> --out /bench/.../chatbot/components.json
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, "/app")

from pgvector import Vector

from app.workflow.providers import get_embedding, get_vlm
from app.workflow.retrieval import Retriever, rrf_fuse


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
    }


async def measure_retriever(course_id: str, query: str, hyde: str, iterations: int) -> dict:
    retriever = Retriever()
    embeddings = get_embedding()
    embed_q: list[float] = []
    embed_h: list[float] = []
    bm25: list[float] = []
    dense: list[float] = []
    hyde_dense: list[float] = []
    fuse: list[float] = []
    total: list[float] = []
    query_vector = await embeddings.aembed_query(query)
    hyde_vector = await embeddings.aembed_query(hyde) if hyde else None

    for _ in range(iterations):
        started = time.perf_counter()
        qv = await embeddings.aembed_query(query)
        embed_q.append((time.perf_counter() - started) * 1000)
        if hyde:
            started = time.perf_counter()
            hv = await embeddings.aembed_query(hyde)
            embed_h.append((time.perf_counter() - started) * 1000)
        else:
            hv = None

        started = time.perf_counter()
        b = await asyncio.to_thread(retriever._search_bm25, query, course_id)
        bm25.append((time.perf_counter() - started) * 1000)
        started = time.perf_counter()
        d = await asyncio.to_thread(
            retriever._search_dense, Vector(qv), course_id, retriever.dense_candidates
        )
        dense.append((time.perf_counter() - started) * 1000)
        if hv is not None:
            started = time.perf_counter()
            h = await asyncio.to_thread(
                retriever._search_dense, Vector(hv), course_id, retriever.hyde_candidates
            )
            hyde_dense.append((time.perf_counter() - started) * 1000)
        started = time.perf_counter()
        branches = [(b, 1.0), (d, 1.0)]
        if hv is not None:
            branches.append((h, retriever.hyde_weight))
        rrf_fuse(branches, retriever.rrf_k, retriever.top_k)
        fuse.append((time.perf_counter() - started) * 1000)

        started = time.perf_counter()
        await retriever.asearch(query, hyde, course_id)
        total.append((time.perf_counter() - started) * 1000)

    retriever.close()
    return {
        "query": query,
        "hyde": bool(hyde),
        "iterations": iterations,
        "embed_query_ms": summarize(embed_q),
        "embed_hyde_ms": summarize(embed_h),
        "bm25_ms": summarize(bm25),
        "dense_ms": summarize(dense),
        "hyde_dense_ms": summarize(hyde_dense),
        "rrf_fuse_ms": summarize(fuse),
        "asearch_total_ms": summarize(total),
        "query_dim": len(query_vector),
        "hyde_dim": len(hyde_vector) if hyde_vector else None,
    }


async def measure_llm(concurrency: int, iterations: int) -> dict:
    from app.workflow.llm import get_llm_client

    client = get_llm_client()
    prompt = [
        {"role": "system", "content": "Trả lời ngắn gọn bằng tiếng Việt."},
        {"role": "user", "content": "Giải thích embedding là gì trong 2 câu."},
    ]
    sem = asyncio.Semaphore(concurrency)
    ttfts: list[float] = []
    totals: list[float] = []
    chunks: list[int] = []

    async def one():
        async with sem:
            started = time.perf_counter()
            first = None
            count = 0
            async for _ in client.stream(prompt):
                if first is None:
                    first = time.perf_counter()
                count += 1
            end = time.perf_counter()
            ttfts.append((first - started) * 1000 if first else 0.0)
            totals.append((end - started) * 1000)
            chunks.append(count)

    await asyncio.gather(*(one() for _ in range(iterations)))
    return {
        "concurrency": concurrency,
        "iterations": iterations,
        "ttft_ms": summarize(ttfts),
        "total_ms": summarize(totals),
        "chunks": summarize([float(c) for c in chunks]),
    }


def measure_embedding(iterations: int) -> dict:
    embedding = get_embedding()
    docs = [
        "Machine learning is a field of study.",
        "Embeddings map text to dense vectors.",
        "Vector search finds nearest neighbours.",
        "Retrieval augmented generation grounds answers.",
    ]
    batch_ms: list[float] = []
    query_ms: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        embedding.embed_documents(docs)
        batch_ms.append((time.perf_counter() - started) * 1000)
        started = time.perf_counter()
        embedding.embed_query("embedding là gì?")
        query_ms.append((time.perf_counter() - started) * 1000)
    return {
        "batch_docs": len(docs),
        "batch_ms": summarize(batch_ms),
        "query_ms": summarize(query_ms),
    }


def measure_vlm(pdf: str, iterations: int) -> dict:
    import pymupdf
    from langchain_core.messages import HumanMessage, SystemMessage

    from app.workflow.prompts import SLIDE_VLM_PROMPT

    doc = pymupdf.open(pdf)
    page = doc[0]
    pix = page.get_pixmap(dpi=120, alpha=False)
    b64 = base64.b64encode(pix.tobytes("png")).decode("ascii")
    doc.close()
    vlm = get_vlm()
    times: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        vlm.invoke(
            [
                SystemMessage(content=SLIDE_VLM_PROMPT),
                HumanMessage(
                    content=[
                        {"type": "text", "text": "Chuyển slide sau thành text."},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ]
                ),
            ]
        )
        times.append((time.perf_counter() - started) * 1000)
    return {"iterations": iterations, "vlm_total_ms": summarize(times)}


async def main_async(args) -> dict:
    result = {"mode": args.mode}
    if args.mode in {"retriever", "all"}:
        result["retriever"] = await measure_retriever(
            args.course_id, args.query, args.hyde, args.iterations
        )
    if args.mode in {"llm", "all"}:
        result["llm"] = await measure_llm(args.concurrency, args.iterations)
    if args.mode in {"embedding", "all"}:
        result["embedding"] = measure_embedding(args.iterations)
    if args.mode in {"vlm", "all"} and args.pdf:
        result["vlm"] = measure_vlm(args.pdf, max(1, args.iterations // 10))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=["retriever", "llm", "embedding", "vlm", "all"], default="all"
    )
    parser.add_argument("--course-id", required=True)
    parser.add_argument("--query", default="Giải thích embedding và vector search trong bài giảng.")
    parser.add_argument(
        "--hyde",
        default="Embedding là vector biểu diễn văn bản; vector search tìm lân cận gần nhất.",
    )
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--pdf", default="")
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
