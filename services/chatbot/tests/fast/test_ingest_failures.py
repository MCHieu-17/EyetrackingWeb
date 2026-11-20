"""Ingest failures: partial, all VLM down, file/page lỗi."""

from __future__ import annotations

import uuid

import pytest

from tests.support import db
from tests.support.pdf import make_corrupt_pdf, make_pdf

pytestmark = pytest.mark.fast


async def test_partial_vlm_failure_returns_counts(client, fake_providers):
    key = f"test/{uuid.uuid4().hex}.pdf"
    make_pdf(key, ["alpha", "beta"])
    seeded = db.seed_course(pdf_object_key=key, index_status="pending")
    fake_providers.vlm.fail_first = True

    response = await client.post(
        "/ingest/slides", json={"slide_ids": seeded["slide_ids"]}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["processed"] == 1
    assert body["failed"] == 1
    assert len(body["errors"]) == 1
    statuses = {
        row["index_status"]
        for row in db.fetch_all("SELECT index_status FROM slides")
    }
    assert statuses == {"ready", "failed"}
    failed = db.fetch_one(
        "SELECT index_error FROM slides WHERE index_status = 'failed'"
    )
    assert "VLM tạm thời" in failed["index_error"]


async def test_all_vlm_down_returns_503(client, fake_providers):
    key = f"test/{uuid.uuid4().hex}.pdf"
    make_pdf(key, ["alpha", "beta"])
    seeded = db.seed_course(pdf_object_key=key, index_status="pending")
    fake_providers.vlm.fail_all = True

    response = await client.post(
        "/ingest/slides", json={"slide_ids": seeded["slide_ids"]}
    )
    assert response.status_code == 503
    assert (
        db.fetch_one(
            "SELECT count(*) AS n FROM slides WHERE index_status = 'failed'"
        )["n"]
        == 2
    )


async def test_missing_pdf_marks_slides_failed(client, fake_providers):
    seeded = db.seed_course(
        pdf_object_key=f"missing/{uuid.uuid4().hex}.pdf",
        index_status="pending",
    )
    response = await client.post(
        "/ingest/slides", json={"slide_ids": seeded["slide_ids"]}
    )
    assert response.status_code == 200
    assert response.json()["processed"] == 0
    assert response.json()["failed"] == 2
    assert fake_providers.vlm.calls == 0


async def test_corrupt_pdf_marks_slide_failed(client, fake_providers):
    key = f"test/{uuid.uuid4().hex}.pdf"
    make_corrupt_pdf(key)
    seeded = db.seed_course(
        slide_transcripts=["alpha"], pdf_object_key=key, index_status="pending"
    )
    response = await client.post(
        "/ingest/slides", json={"slide_ids": seeded["slide_ids"][:1]}
    )
    assert response.status_code == 200
    assert response.json()["processed"] == 0
    assert response.json()["failed"] == 1
    row = db.fetch_one("SELECT index_status, index_error FROM slides")
    assert row["index_status"] == "failed"
    assert row["index_error"]


async def test_pdf_page_out_of_range_marks_slide_failed(client, fake_providers):
    key = f"test/{uuid.uuid4().hex}.pdf"
    make_pdf(key, ["alpha"])
    seeded = db.seed_course(
        slide_transcripts=["alpha", "beta"], pdf_object_key=key,
        index_status="pending",
    )
    response = await client.post(
        "/ingest/slides", json={"slide_ids": [seeded["slide_ids"][1]]}
    )
    assert response.status_code == 200
    assert response.json()["processed"] == 0
    assert response.json()["failed"] == 1
    row = db.fetch_one(
        "SELECT index_status, index_error FROM slides WHERE position = 1"
    )
    assert row["index_status"] == "failed"
    assert "ngoài PDF" in row["index_error"]
