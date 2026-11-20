"""Tạo PDF mẫu cho ingest test."""

from __future__ import annotations

import os
from pathlib import Path

import pymupdf


def media_dir() -> Path:
    path = Path(os.environ.get("LOCAL_MEDIA_DIR", "/tmp/chatbot-media"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_pdf(object_key: str, lines: list[str]) -> bytes:
    doc = pymupdf.open()
    for line in lines:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 96), line, fontsize=24)
    data = doc.tobytes()
    doc.close()
    target = media_dir() / object_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return data


def make_corrupt_pdf(object_key: str) -> bytes:
    data = b"not a real pdf"
    target = media_dir() / object_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return data
