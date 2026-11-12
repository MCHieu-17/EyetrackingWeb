"""Tests cho parse/validate citation tối giản."""

from app.workflow.citations import (
    citation_ids,
    has_valid_citation,
    strip_invalid_citations,
    valid_citation_ids,
)


def test_citation_ids_returns_all_numbers_in_order():
    assert citation_ids("A [1] B [3][2] C") == [1, 3, 2]
    assert citation_ids("không có citation") == []


def test_valid_citation_ids_filters_out_of_range():
    assert valid_citation_ids("A [1] B [3] C [0] D [9]", 3) == [1, 3]


def test_has_valid_citation():
    assert has_valid_citation("A [2]", 3) is True
    assert has_valid_citation("A [4]", 3) is False
    assert has_valid_citation("không có", 3) is False


def test_strip_invalid_citations_removes_only_invalid():
    assert strip_invalid_citations("A [1] B [4] C [2]", 3) == "A [1] B  C [2]"
    assert strip_invalid_citations("A [0] B [9]", 3) == "A  B "
