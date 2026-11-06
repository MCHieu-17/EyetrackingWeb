import json
import struct

from app.protocol import parse_frame


def _frame(header: dict, jpeg: bytes) -> bytes:
    raw = json.dumps(header).encode()
    return struct.pack(">I", len(raw)) + raw + jpeg


def test_parse_v2_frame():
    header = {
        "v": 2,
        "frameId": "f-1",
        "sequence": 3,
        "captureMonotonicNs": 123,
        "presentationId": "p-1",
        "layoutGeneration": 2,
    }
    parsed, jpeg = parse_frame(_frame(header, b"jpeg-bytes"))
    assert parsed == header
    assert jpeg == b"jpeg-bytes"


def test_legacy_jpeg_passthrough():
    parsed, jpeg = parse_frame(b"\xff\xd8\xff\xe0raw-jpeg")
    assert parsed is None
    assert jpeg == b"\xff\xd8\xff\xe0raw-jpeg"


def test_invalid_header_length_passthrough():
    data = struct.pack(">I", 999999) + b"short"
    parsed, jpeg = parse_frame(data)
    assert parsed is None
    assert jpeg == data


def test_wrong_version_passthrough():
    raw = json.dumps({"v": 1, "frameId": "old"}).encode()
    data = struct.pack(">I", len(raw)) + raw + b"jpeg"
    parsed, jpeg = parse_frame(data)
    assert parsed is None
    assert jpeg == data
