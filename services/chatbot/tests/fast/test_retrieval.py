"""Retrieval SQL mới: course scope, threshold sau LIMIT, hydrate, context budget."""

from __future__ import annotations

import pytest

from app.workflow.retrieval import format_context, get_retriever
from tests.support import db

pytestmark = pytest.mark.fast


async def test_retrieval_hydrates_top_doc_and_scopes_course(fake_providers):
    seeded = db.seed_course(slide_transcripts=["alpha", "beta"])
    db.seed_course(slide_transcripts=["alpha"])

    docs = await get_retriever().asearch("alpha", "", seeded["course_id"])

    assert docs
    top = docs[0]
    assert str(top["id"]) == seeded["slide_ids"][0]
    assert top["content"] == "alpha"
    assert str(top["course_id"]) == seeded["course_id"]
    assert str(top["lesson_id"]) == seeded["lesson_id"]
    assert top["module_title"] == "Chương 1"
    assert top["lesson_title"] == "Bài 1"
    assert top["slide_index"] == 0
    assert top["score"] > 0
    assert all(str(doc["course_id"]) == seeded["course_id"] for doc in docs)


async def test_dense_threshold_filters_weak_matches(fake_providers):
    seeded = db.seed_course(slide_transcripts=["beta"])

    docs = await get_retriever().asearch("alpha", "", seeded["course_id"])

    assert docs == []


async def test_unpublished_course_is_not_retrieved(fake_providers):
    seeded = db.seed_course(published=False, slide_transcripts=["alpha"])

    docs = await get_retriever().asearch("alpha", "", seeded["course_id"])

    assert docs == []


def test_format_context_keeps_every_doc_within_budget():
    filler = "x" * 8_000
    content = f"{filler} needle {filler}"
    docs = [
        {
            "id": index,
            "module_title": "Module",
            "lesson_title": "Lesson",
            "slide_index": index,
            "content": content,
        }
        for index in range(1, 9)
    ]

    text = format_context(docs, "needle")

    assert len(text) <= 20_000
    assert text.count("needle") == len(docs)
    for index in range(1, 9):
        assert f"[{index}] Module > Lesson (slide {index})" in text
