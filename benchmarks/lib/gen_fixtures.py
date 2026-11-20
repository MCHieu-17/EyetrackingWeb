#!/usr/bin/env python3
"""Sinh PDF mẫu cố định cho benchmark ingest.

Chạy trong image chatbot (có pymupdf):
    docker compose ... exec -T chatbot \
      python /bench/lib/gen_fixtures.py --out /bench/fixtures/lecture_20p.pdf

Nội dung dùng ASCII để không phụ thuộc font tiếng Việt; mục tiêu là đo
render/VLM/embedding, không phải chất lượng ngôn ngữ.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover - fallback nếu chạy trong image khác
    import fitz  # type: ignore


TOPICS = [
    ("Introduction to Machine Learning", "Supervised learning uses labelled data."),
    ("Linear Regression", "Minimize mean squared error with gradient descent."),
    ("Logistic Regression", "Predict probabilities with the sigmoid function."),
    ("Decision Trees", "Split features to reduce impurity."),
    ("Model Evaluation", "Use train/validation/test splits and cross-validation."),
    ("Overfitting", "Regularization limits model complexity."),
    ("Neural Networks", "Stack linear layers with non-linear activations."),
    ("Embeddings", "Map text to dense vectors for semantic retrieval."),
    ("Vector Search", "Approximate nearest neighbours trade recall for speed."),
    ("Retrieval Augmented Generation", "Retrieve course slides before answering."),
]


def _page_text(page: fitz.Page, topic: tuple[str, str], index: int, total: int) -> None:
    title, body = topic
    page.insert_text(
        (56, 70), f"Benchmark Lecture {index + 1}/{total}", fontsize=11, fontname="helv"
    )
    page.insert_text((56, 105), title, fontsize=22, fontname="helv")
    page.insert_text((56, 135), body, fontsize=12, fontname="helv")
    # Đoạn văn dài để VLM có nội dung transcribe.
    lines = [
        "This slide is part of a deterministic benchmark fixture.",
        "The goal is to measure PDF rendering, vision-language transcription,",
        "embedding generation, and vector upsert under a fixed workload.",
        "Numbers and tables below are synthetic and do not represent real data.",
    ]
    y = 175
    for line in lines:
        page.insert_text((56, y), line, fontsize=11, fontname="helv")
        y += 18

    # Bảng 4x4 đơn giản.
    x0, y0, cell_w, cell_h = 56, 270, 105, 26
    for row in range(4):
        for col in range(4):
            page.draw_rect(
                fitz.Rect(
                    x0 + col * cell_w,
                    y0 + row * cell_h,
                    x0 + (col + 1) * cell_w,
                    y0 + (row + 1) * cell_h,
                ),
                color=(0.3, 0.3, 0.3),
                width=0.5,
            )
            page.insert_text(
                (x0 + col * cell_w + 6, y0 + row * cell_h + 17),
                f"R{row}C{col}",
                fontsize=8,
                fontname="helv",
            )

    # Hình khối đơn giản để trang image-heavy.
    if index % 3 == 0:
        page.draw_circle((430, 480), 55, color=(0.2, 0.4, 0.8), width=2)
        page.draw_line((375, 480), (485, 480), color=(0.2, 0.4, 0.8), width=2)
        page.draw_line((430, 425), (430, 535), color=(0.2, 0.4, 0.8), width=2)
        page.insert_text((360, 560), "Figure: synthetic diagram", fontsize=9, fontname="helv")

    page.insert_text((56, 790), f"page={index + 1} deterministic=true", fontsize=8, fontname="helv")


def build(out: Path, pages: int) -> dict:
    doc = fitz.open()
    doc.set_metadata(
        {
            "title": "EyeLearning benchmark fixture",
            "author": "benchmark",
            "creationDate": "D:20260101000000Z",
            "modDate": "D:20260101000000Z",
        }
    )
    for index in range(pages):
        page = doc.new_page(width=595, height=842)
        topic = TOPICS[index % len(TOPICS)]
        _page_text(page, topic, index, pages)
    try:
        data = doc.tobytes(garbage=4, deflate=True, no_new_id=True)
    except TypeError:
        data = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    return {
        "path": str(out),
        "pages": pages,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="benchmarks/fixtures/lecture_20p.pdf")
    parser.add_argument("--pages", type=int, default=20)
    parser.add_argument("--meta", default="")
    args = parser.parse_args()
    meta = build(Path(args.out), args.pages)
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    if args.meta:
        Path(args.meta).write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
