"""Tests cho protocol v2 của gaze WebSocket."""

import json
import struct

from app.protocol import apply_header_echo, parse_frame


def _frame(header: dict, jpeg: bytes = b"\xff\xd8jpeg") -> bytes:
    raw = json.dumps(header).encode()
    return struct.pack(">I", len(raw)) + raw + jpeg


def test_parse_v2_frame_returns_header_and_jpeg():
    header = {
        "v": 2,
        "frameId": "f-1",
        "sequence": 7,
        "captureMonotonicNs": 42,
        "presentationId": "p-1",
        "layoutGeneration": 3,
    }
    parsed, jpeg = parse_frame(_frame(header))
    assert parsed == header
    assert jpeg == b"\xff\xd8jpeg"


def test_parse_legacy_jpeg_and_malformed_frames():
    assert parse_frame(b"\xff\xd8legacy") == (None, b"\xff\xd8legacy")
    assert parse_frame(b"") == (None, b"")
    assert parse_frame(b"\x00") == (None, b"\x00")


def test_parse_rejects_invalid_length_and_non_v2_header():
    too_long = struct.pack(">I", 100) + b"{}"
    assert parse_frame(too_long) == (None, too_long)
    wrong_version = _frame({"v": 1, "frameId": "f"})
    assert parse_frame(wrong_version) == (None, wrong_version)


def test_apply_header_echo_only_returns_known_fields():
    response = {"ok": True, "status": "ok", "x": 0.2, "y": 0.3}
    header = {
        "v": 2,
        "frameId": "f-1",
        "sequence": 9,
        "captureMonotonicNs": 123,
        "eventTime": "2026-01-01T00:00:00.000Z",
        "presentationId": "p-1",
        "layoutGeneration": 4,
        "untrusted": "ignored",
    }
    assert apply_header_echo(response, header) == {
        **response,
        "frameId": "f-1",
        "sequence": 9,
        "captureMonotonicNs": 123,
        "eventTime": "2026-01-01T00:00:00.000Z",
        "presentationId": "p-1",
        "layoutGeneration": 4,
    }
    assert apply_header_echo(response, None) == response
