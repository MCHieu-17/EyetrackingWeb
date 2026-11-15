"""Tests cho RRF fusion, citation building và format context."""

from app.workflow.retrieval import build_citations, format_context, rrf_fuse


def _doc(doc_id: str, *, title: str = "Bài 1", slide: int = 1) -> dict:
    return {
        "id": doc_id,
        "course_id": "course-1",
        "lesson_id": "lesson-1",
        "slide_id": "slide-1",
        "asset_id": "asset-1",
        "pdf_object_key": "pdf/key.pdf",
        "pdf_storage_backend": "local",
        "pdf_mime_type": "application/pdf",
        "source_page": 2,
        "content": f"Nội dung {doc_id}",
        "slide_title": "Slide",
        "module_title": "Chương 1",
        "lesson_title": title,
        "slide_index": slide,
    }


def test_rrf_fuse_orders_by_weighted_rank():
    first = [_doc("1"), _doc("2")]
    second = [_doc("2"), _doc("3")]

    result = rrf_fuse([(first, 1.0), (second, 1.0)], k=60, top_k=3)

    assert [doc["id"] for doc in result] == ["2", "1", "3"]
    assert result[0]["score"] > result[1]["score"]


def test_rrf_fuse_dedupes_and_applies_weight():
    first = [_doc("1"), _doc("2")]
    second = [_doc("2"), _doc("1")]

    result = rrf_fuse([(first, 1.0), (second, 0.5)], k=60, top_k=2)

    assert len(result) == 2
    assert {doc["id"] for doc in result} == {"1", "2"}


def test_rrf_fuse_respects_top_k():
    first = [_doc(str(index)) for index in range(5)]

    result = rrf_fuse([(first, 1.0)], k=60, top_k=2)

    assert [doc["id"] for doc in result] == ["0", "1"]


def test_build_citations_shape():
    citations = build_citations([_doc("doc-1", title="Bài 2", slide=3)])

    assert len(citations) == 1
    citation = citations[0]
    assert citation["document_id"] == "doc-1"
    assert citation["title"] == "Chương 1 - Bài 2"
    assert citation["slide_index"] == 3
    assert citation["pdf_url"] == "/media/assets/asset-1/file"
    assert citation["location"] == "pdf/key.pdf#page=2"
    assert citation["snippet"] == "Nội dung doc-1"


def test_format_context_numbers_documents():
    text = format_context([_doc("1"), _doc("2", title="Bài 2", slide=2)])

    assert text.startswith("[1] Chương 1 > Bài 1 (slide 1)")
    assert "[2] Chương 1 > Bài 2 (slide 2)" in text
    assert "Nội dung 1" in text
    assert "Nội dung 2" in text
