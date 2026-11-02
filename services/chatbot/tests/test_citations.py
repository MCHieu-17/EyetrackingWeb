from app.workflow.citations import (
    chunk_text,
    claim_in_answer,
    extract_citation_ids,
    quote_supported,
    sanitize_citations,
)


def test_extract_citation_ids():
    assert extract_citation_ids("A [1], B [2] và [10].") == [1, 2, 10]


def test_sanitize_citations_removes_invalid():
    citations = [{"document_id": "a"}, {"document_id": "b"}]
    assert sanitize_citations("A [1], B [3], C [2].", citations) == "A [1], B, C [2]."


def test_sanitize_citations_keeps_valid():
    citations = [{"document_id": "a"}]
    assert sanitize_citations("A [1].", citations) == "A [1]."


def test_quote_supported_exact():
    doc = "Khóa chính (primary key) xác định duy nhất mỗi hàng."
    assert quote_supported("Khóa chính xác định duy nhất mỗi hàng", doc)


def test_quote_supported_fake():
    doc = "Khóa chính xác định duy nhất mỗi hàng."
    assert not quote_supported("Khóa ngoại liên kết hai bảng", doc)


def test_quote_supported_short_quote_rejected():
    assert not quote_supported("abc", "abc def ghi")


def test_claim_in_answer():
    answer = "Khóa chính xác định duy nhất mỗi hàng trong bảng."
    assert claim_in_answer("Khóa chính xác định duy nhất mỗi hàng", answer)
    assert not claim_in_answer("Khóa ngoại liên kết hai bảng", answer)


def test_chunk_text_preserves_spaces():
    text = "Một hai ba bốn năm sáu bảy tám chín mười"
    chunks = chunk_text(text, size=10)
    assert "".join(chunks) == text
    assert all(chunk for chunk in chunks)


def test_chunk_text_empty():
    assert chunk_text("") == []
