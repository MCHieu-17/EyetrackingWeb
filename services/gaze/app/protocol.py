"""Protocol v2 cho frame gaze: 4-byte header length + JSON header + JPEG.

JPEG được trả dưới dạng `memoryview` để không copy toàn bộ payload mỗi frame;
`cv2.imdecode`/`np.frombuffer` đọc trực tiếp view này.
"""

from __future__ import annotations

import json
import struct


def parse_frame(
    data: bytes | bytearray | memoryview,
) -> tuple[dict | None, memoryview]:
    """Trả (header, jpeg). Header None = JPEG legacy (client cũ)."""
    view = memoryview(data)
    if len(view) < 4:
        return None, view
    header_len = struct.unpack_from(">I", view, 0)[0]
    if header_len <= 0 or header_len > 64 * 1024 or len(view) < 4 + header_len:
        return None, view
    try:
        header = json.loads(bytes(view[4 : 4 + header_len]))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, view
    if not isinstance(header, dict) or header.get("v") != 2:
        return None, view
    return header, view[4 + header_len :]


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
