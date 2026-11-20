"""Ingest API: auth, happy path, idempotency, metadata, reindex."""

from __future__ import annotations

import uuid

import httpx
import pytest

from tests.support import db
from tests.support.pdf import make_pdf

pytestmark = pytest.mark.fast


async def test_ingest_requires_internal_token(fake_providers):
    transport = httpx.ASGITransport(app=__import__("app.main", fromlist=["app"]).app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/ingest/slides", json={"slide_ids": [str(uuid.uuid4())]}
        )
    assert response.status_code == 401


async def test_ingest_happy_path_keeps_metadata_and_vector(client, fake_providers):
    key = f"test/{uuid.uuid4().hex}.pdf"
    make_pdf(key, ["alpha page one", "beta page two"])
    seeded = db.seed_course(
        slide_transcripts=["old alpha", "old beta"], pdf_object_key=key,
        index_status="pending"
    )
    response = await client.post(
        "/ingest/slides", json={"slide_ids": seeded["slide_ids"]}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"processed": 2, "failed": 0, "errors": []}
    assert fake_providers.vlm.calls == 2
    assert fake_providers.embedding.documents

    rows = db.fetch_all(
        "SELECT id, transcript, embedding IS NOT NULL AS has_embedding, "
        "index_status, pipeline_version, model_version, index_error "
        "FROM slides ORDER BY position"
    )
    assert len(rows) == 2
    for row in rows:
        assert row["transcript"] == "Nội dung slide alpha"
        assert row["has_embedding"] is True
        assert row["index_status"] == "ready"
        assert row["pipeline_version"] == "rag-v2"
        assert row["model_version"] == "Qwen/Qwen3-Embedding-0.6B"
        assert row["index_error"] is None

    docs = db.fetch_all(
        "SELECT slide_id, course_id, lesson_id, source_page, slide_title, "
        "pdf_asset_id FROM v_chatbot_slide_documents ORDER BY source_page"
    )
    assert [str(row["slide_id"]) for row in docs] == seeded["slide_ids"]
    assert {str(row["course_id"]) for row in docs} == {seeded["course_id"]}
    assert [row["source_page"] for row in docs] == [1, 2]


async def test_ingest_skips_ready_slides(client, fake_providers):
    key = f"test/{uuid.uuid4().hex}.pdf"
    make_pdf(key, ["alpha", "beta"])
    seeded = db.seed_course(pdf_object_key=key, index_status="pending")
    first = await client.post(
        "/ingest/slides", json={"slide_ids": seeded["slide_ids"]}
    )
    assert first.json()["processed"] == 2
    calls = fake_providers.vlm.calls

    second = await client.post(
        "/ingest/slides", json={"slide_ids": seeded["slide_ids"]}
    )
    assert second.status_code == 200
    assert second.json() == {"processed": 0, "failed": 0, "errors": []}
    assert fake_providers.vlm.calls == calls


async def test_ingest_reindex_updates_in_place(client, fake_providers):
    key = f"test/{uuid.uuid4().hex}.pdf"
    make_pdf(key, ["alpha", "beta"])
    seeded = db.seed_course(pdf_object_key=key, index_status="pending")
    await client.post("/ingest/slides", json={"slide_ids": seeded["slide_ids"]})

    db.execute(
        "UPDATE slides SET index_status = 'pending', transcript = 'old' "
        "WHERE id = ANY(%s::uuid[])",
        (seeded["slide_ids"],),
    )
    fake_providers.vlm.transcript = "Nội dung mới alpha"
    reindex = await client.post(
        "/ingest/slides", json={"slide_ids": seeded["slide_ids"]}
    )
    assert reindex.status_code == 200
    assert reindex.json()["processed"] == 2
    rows = db.fetch_all(
        "SELECT transcript FROM slides WHERE id = ANY(%s::uuid[])",
        (seeded["slide_ids"],),
    )
    assert {row["transcript"] for row in rows} == {"Nội dung mới alpha"}
    assert db.fetch_one("SELECT count(*) AS n FROM slides")["n"] == 2


async def test_ingest_unknown_slide_returns_404(client, fake_providers):
    response = await client.post(
        "/ingest/slides", json={"slide_ids": [str(uuid.uuid4())]}
    )
    assert response.status_code == 404


async def test_ingest_request_validation(client, fake_providers):
    assert (
        await client.post("/ingest/slides", json={"slide_ids": []})
    ).status_code == 422
    too_many = [str(uuid.uuid4()) for _ in range(2001)]
    assert (
        await client.post("/ingest/slides", json={"slide_ids": too_many})
    ).status_code == 422


async def test_ingest_keeps_one_document_per_slide(client, fake_providers):
    key = f"test/{uuid.uuid4().hex}.pdf"
    long_text = "alpha " * 5000
    make_pdf(key, [long_text])
    seeded = db.seed_course(
        slide_transcripts=[long_text], pdf_object_key=key, index_status="pending"
    )
    fake_providers.vlm.transcript = long_text
    response = await client.post(
        "/ingest/slides", json={"slide_ids": seeded["slide_ids"][:1]}
    )
    assert response.status_code == 200
    assert db.fetch_one("SELECT count(*) AS n FROM slides")["n"] == 1
    assert (
        db.fetch_one("SELECT count(*) AS n FROM v_chatbot_slide_documents")["n"]
        == 1
    )
