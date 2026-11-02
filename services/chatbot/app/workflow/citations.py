"""Tiện ích citation: parse, sanitize, so khớp evidence quote.

Citation do LLM sinh ra không được tin tuyệt đối:
- Chỉ giữ [n] nằm trong khoảng 1..len(citations).
- Verifier phải trả `evidence_quote`; code kiểm tra quote thật sự có trong
  tài liệu được cite (exact substring, fallback token overlap).
"""

import re
import unicodedata

CITE_RE = re.compile(r"\[(\d+)\]")
WORD_RE = re.compile(r"\w+", re.UNICODE)


def extract_citation_ids(text: str) -> list[int]:
    return [int(match.group(1)) for match in CITE_RE.finditer(text or "")]


def sanitize_citations(text: str, citations: list[dict]) -> str:
    """Bỏ các nhãn [n] không tồn tại; giữ nguyên phần còn lại."""
    limit = len(citations)

    def _replace(match: re.Match) -> str:
        index = int(match.group(1))
        return match.group(0) if 1 <= index <= limit else ""

    cleaned = CITE_RE.sub(_replace, text or "")
    # Dọn khoảng trắng thừa do bỏ citation (không đụng newline).
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" +([.,;:!?])", r"\1", cleaned)
    return cleaned.strip()


def normalize_text(text: str) -> str:
    """Chuẩn hoá để so khớp quote: NFC, lowercase, gộp whitespace."""
    text = unicodedata.normalize("NFC", text or "").lower()
    return re.sub(r"\s+", " ", text).strip()


def quote_supported(quote: str, document: str) -> bool:
    """True nếu quote thật sự xuất hiện trong document.

    Ưu tiên exact substring sau normalize. Nếu model trích hơi khác dấu câu,
    cho phép fallback token overlap >= 0.85 (nhưng quote phải đủ dài).
    """
    q = normalize_text(quote)
    d = normalize_text(document)
    if not q or not d:
        return False

    # Quote quá ngắn không đủ để chứng minh một claim (vd "abc").
    q_tokens = WORD_RE.findall(q)
    if len(q_tokens) < 4:
        return False
    if q in d:
        return True

    d_tokens = set(WORD_RE.findall(d))
    overlap = sum(1 for token in q_tokens if token in d_tokens) / len(q_tokens)
    return overlap >= 0.85


def claim_in_answer(claim: str, answer: str) -> bool:
    """True nếu claim verifier trả về thật sự có trong answer.

    Chặn trường hợp verifier bịa thêm claim không tồn tại để đánh giá.
    """
    c = normalize_text(claim)
    a = normalize_text(answer)
    if not c or not a:
        return False
    if c in a:
        return True

    c_tokens = WORD_RE.findall(c)
    if len(c_tokens) < 4:
        return False
    a_tokens = set(WORD_RE.findall(a))
    overlap = sum(1 for token in c_tokens if token in a_tokens) / len(c_tokens)
    return overlap >= 0.8


def chunk_text(text: str, size: int = 48) -> list[str]:
    """Chia answer thành chunk nhỏ để stream sau khi verify.

    Cắt theo ranh giới từ để frontend render Markdown mượt hơn.
    """
    if not text:
        return []
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for word in text.split(" "):
        piece = word if not current else " " + word
        if length + len(piece) > size and current:
            chunks.append("".join(current))
            # Giữ khoảng trắng ở ranh giới chunk: frontend nối token trực tiếp.
            current = [" " + word]
            length = 1 + len(word)
        else:
            current.append(piece)
            length += len(piece)
    if current:
        chunks.append("".join(current))
    return chunks
