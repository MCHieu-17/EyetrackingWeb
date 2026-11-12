"""Tiện ích citation tối giản.

Không còn LLM verifier. Citation do model sinh ra được kiểm tra bằng code:
- Chỉ chấp nhận [n] nằm trong khoảng 1..len(citations).
- Citation sai bị bỏ khỏi câu trả lời (non-streaming) hoặc bị frontend bỏ qua
  (streaming, vì frontend đã kiểm tra n < 1 || n > count).
"""

import re

CITATION_RE = re.compile(r"\[(\d+)\]")


def citation_ids(text: str) -> list[int]:
    """Trả về tất cả số citation xuất hiện trong text, theo thứ tự."""
    return [int(number) for number in CITATION_RE.findall(text or "")]


def valid_citation_ids(text: str, count: int) -> list[int]:
    """Trả về các citation hợp lệ trong khoảng 1..count."""
    return [number for number in citation_ids(text) if 1 <= number <= count]


def has_valid_citation(text: str, count: int) -> bool:
    """True nếu text có ít nhất một citation hợp lệ."""
    return bool(valid_citation_ids(text, count))


def strip_invalid_citations(text: str, count: int) -> str:
    """Bỏ các citation nằm ngoài khoảng 1..count."""

    def replace(match: re.Match[str]) -> str:
        number = int(match.group(1))
        return match.group(0) if 1 <= number <= count else ""

    return CITATION_RE.sub(replace, text or "")
