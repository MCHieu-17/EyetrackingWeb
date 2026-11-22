"""Protocol v2: JPEG được trả bằng memoryview, không copy payload."""

from __future__ import annotations

import json
import struct

import pytest

from app.protocol import parse_frame

pytestmark = pytest.mark.fast


def _frame(header: dict | None, jpeg: bytes = b"\xff\xd8payload\xff\xd9") -> bytes:
    if header is None:
        return jpeg
    raw = json.dumps(header).encode()
    return struct.pack(">I", len(raw)) + raw + jpeg


def test_v2_header_returns_memoryview_without_copy():
    header = {"v": 2, "frameId": "f-1", "sequence": 3}
    raw = _frame(header)
    parsed, jpeg = parse_frame(raw)

    assert parsed == header
    assert isinstance(jpeg, memoryview)
    assert jpeg.obj is raw
    assert jpeg.tobytes() == b"\xff\xd8payload\xff\xd9"


def test_legacy_jpeg_is_the_whole_view():
    raw = _frame(None)
    header, jpeg = parse_frame(raw)

    assert header is None
    assert jpeg.obj is raw
    assert jpeg.tobytes() == raw


def test_wrong_version_falls_back_to_raw_jpeg():
    raw = _frame({"v": 1, "frameId": "old"})
    header, jpeg = parse_frame(raw)

    assert header is None
    assert jpeg.tobytes() == raw


def test_short_or_corrupt_header_falls_back_to_raw():
    assert parse_frame(b"abc") == (None, memoryview(b"abc"))

    raw = struct.pack(">I", 2) + b"{" + b"jpeg"
    header, jpeg = parse_frame(raw)
    assert header is None
    assert jpeg.tobytes() == raw
