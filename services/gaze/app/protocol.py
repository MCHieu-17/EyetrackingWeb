"""Protocol v2 cho frame gaze: 4-byte header length + JSON header + JPEG."""

from __future__ import annotations

import json
import struct


def parse_frame(data: bytes) -> tuple[dict | None, bytes]:
    """Trả (header, jpeg). Header None = JPEG legacy (client cũ)."""
    if len(data) < 4:
        return None, data
    header_len = struct.unpack(">I", data[:4])[0]
    if header_len <= 0 or header_len > 64 * 1024 or len(data) < 4 + header_len:
        return None, data
    try:
        header = json.loads(data[4 : 4 + header_len])
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, data
    if not isinstance(header, dict) or header.get("v") != 2:
        return None, data
    return header, data[4 + header_len :]


_ECHO_FIELDS = (
    "frameId",
    "sequence",
    "captureMonotonicNs",
    "eventTime",
    "presentationId",
    "layoutGeneration",
)


def apply_header_echo(response: dict, header: dict | None) -> dict:
    """Echo các metadata protocol v2 đã biết; bỏ field lạ từ client."""
    if header is None:
        return response
    for field in _ECHO_FIELDS:
        response[field] = header.get(field)
    return response
