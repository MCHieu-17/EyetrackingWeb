"""Upload -> actual chatbot HTTP -> actual isolated PostgreSQL/pgvector.

Run after migrating DATABASE_URL, with CHATBOT_TEST_PYTHON pointing to the
chatbot virtualenv. No external AI calls: providers only are deterministic.
"""

import asyncio
import os
import socket
import subprocess
import time
from pathlib import Path

import httpx
import pymupdf
import pytest
from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal
from app.services import embedding
from tests.conftest import auth
from tests.test_chat import _setup


@pytest.fixture()
def chatbot_http(monkeypatch, tmp_path):
    python = Path(
        os.environ.get(
            "CHATBOT_TEST_PYTHON",
            str(Path(__file__).resolve().parents[2] / "services/chatbot/.venv/bin/python"),
        )
    ).resolve()
    if not python.exists():
        pytest.skip("Set CHATBOT_TEST_PYTHON to chatbot venv")
    root = Path(__file__).resolve().parents[2]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {
        **os.environ,
        "CHATBOT_DATABASE_URL": settings.database_url.replace(
            "postgresql+asyncpg://", "postgresql://"
        ),
        "CHATBOT_INTERNAL_TOKEN": "test-token",
        "RIVER_API_KEY": "fake",
        "LOCAL_MEDIA_DIR": str(settings.media_dir),
        "PYTHONPATH": str(root / "services/chatbot"),
        "EMBEDDING_DIM": "1024",
    }
    log = (tmp_path / "chatbot.log").open("w+")
    process = subprocess.Popen(
        [
            str(python),
            "-m",
            "uvicorn",
            "tests.http_fixture:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=root / "services/chatbot",
        env=env,
        stdout=log,
        stderr=log,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            if process.poll() is not None:
                log.seek(0)
                pytest.fail(log.read())
            try:
                if httpx.get(url + "/ready", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        else:
            pytest.fail("Chatbot test server failed to start")
        monkeypatch.setattr(settings, "chatbot_url", url)
        monkeypatch.setattr(settings, "chatbot_internal_token", "test-token")
        yield url
    finally:
        process.terminate()
        process.wait(timeout=10)
        log.close()


def _pdf(pages=2):
    with pymupdf.open() as doc:
        for i in range(pages):
            page = doc.new_page()
            page.insert_text((50, 50), f"Primary key - page {i + 1}")
        return doc.tobytes()


def _rows(lesson):
    async def run():
        async with SessionLocal() as db:
            return (
                (
                    await db.execute(
                        text("""
                SELECT lc.id, lc.embedding_status, lc.embedding_error, e.content,
                       vector_dims(e.embedding) AS dim, e.metadata,
                       e.course_id, e.lesson_id
                FROM lesson_contents lc LEFT JOIN lesson_content_embedding e ON e.lesson_content_id = lc.id
                WHERE lc.lesson_id = :lesson ORDER BY lc.order_index
            """),
                        {"lesson": lesson},
                    )
                )
                .mappings()
                .all()
            )

    return asyncio.run(run())


def test_pdf_ingest_upsert_retrieval_replace_delete_and_rollback(client, chatbot_http, monkeypatch):
    teacher, student, _, course, _, lesson = _setup(client)
    path = f"/teacher/lessons/{lesson}/slides/upload"

    def upload(data):
        return client.post(
            path, headers=auth(teacher), files={"pdf": ("lesson.pdf", data, "application/pdf")}
        )

    pending_states = []
    actual_call = embedding._call

    async def capture_pending(path, payload):
        async with SessionLocal() as db:
            pending_states.extend(
                (
                    await db.execute(
                        text("SELECT embedding_status FROM lesson_contents WHERE lesson_id=:id"),
                        {"id": lesson},
                    )
                )
                .scalars()
                .all()
            )
        return await actual_call(path, payload)

    monkeypatch.setattr(embedding, "_call", capture_pending)
    response = upload(_pdf())
    assert response.status_code == 201, response.text
    rows = _rows(lesson)
    assert pending_states == ["pending", "pending"]
    assert len(rows) == 2 and all(
        r["embedding_status"] == "ready" and r["dim"] == 1024 for r in rows
    )
    assert all(str(r["course_id"]) == course and str(r["lesson_id"]) == lesson for r in rows)
    assert [r["metadata"]["slide_index"] for r in rows] == [1, 2]
    old_ids = [str(r["id"]) for r in rows]
    # Actual HTTP reingest retains the unique row per slide.
    ingest = httpx.post(
        chatbot_http + "/ingest/lesson",
        headers={"X-Chatbot-Token": "test-token"},
        json={"lesson_id": lesson},
    )
    assert ingest.status_code == 200 and ingest.json()["processed"] == 2
    assert [str(r["id"]) for r in _rows(lesson)] == old_ids
    reply = client.post(
        f"/api/courses/{course}/chat", headers=auth(student), json={"message": "Khóa chính là gì?"}
    )
    assert reply.status_code == 200, reply.text
    assert reply.json()["verified"] and reply.json()["citations"][0]["slideId"] in old_ids
    stream = client.post(
        f"/api/courses/{course}/chat/stream", headers=auth(student), json={"message": "Khóa chính?"}
    )
    assert (
        stream.status_code == 200 and "event: token" in stream.text and "event: done" in stream.text
    )
    # Invalid replacement leaves previous media and vectors intact.
    assert upload(b"not a pdf").status_code == 400
    assert [str(r["id"]) for r in _rows(lesson)] == old_ids

    # A database rollback after rendering must retain old vectors and files too.
    async def block_replacement(create):
        async with SessionLocal() as db:
            if create:
                await db.execute(
                    text(
                        "CREATE TABLE chatbot_test_reference (slide_id uuid REFERENCES lesson_contents(id) ON DELETE RESTRICT)"
                    )
                )
                await db.execute(
                    text("INSERT INTO chatbot_test_reference VALUES (:slide)"),
                    {"slide": old_ids[0]},
                )
            else:
                await db.execute(text("DROP TABLE chatbot_test_reference"))
            await db.commit()

    asyncio.run(block_replacement(True))
    try:
        assert upload(_pdf(1)).status_code == 409
        assert [str(r["id"]) for r in _rows(lesson)] == old_ids
        for row in rows:
            relative = row["metadata"]["image_url"].removeprefix("/media/")
            assert (Path(settings.media_dir) / relative).is_file()
    finally:
        asyncio.run(block_replacement(False))
    assert upload(_pdf(1)).status_code == 201
    current = _rows(lesson)
    assert len(current) == 1 and str(current[0]["id"]) not in old_ids

    async def vector_count(ids):
        async with SessionLocal() as db:
            return (
                await db.execute(
                    text(
                        "SELECT count(*) FROM lesson_content_embedding WHERE lesson_content_id::text = ANY(:ids)"
                    ),
                    {"ids": ids},
                )
            ).scalar_one()

    assert asyncio.run(vector_count(old_ids)) == 0
    assert (
        client.delete(f"/teacher/slides/{current[0]['id']}", headers=auth(teacher)).status_code
        == 200
    )
    assert asyncio.run(vector_count([str(current[0]["id"])])) == 0
    assert upload(_pdf(1)).status_code == 201
    # Adding an image slide also schedules the real HTTP ingest automatically.
    image_name = f"image-{lesson}.png"
    with pymupdf.open() as doc:
        doc.new_page().get_pixmap().save(str(Path(settings.media_dir) / image_name))
    added = client.post(
        f"/teacher/lessons/{lesson}/slides",
        headers=auth(teacher),
        json={"imageUrl": f"/media/{image_name}", "title": "Image slide"},
    )
    assert added.status_code == 201, added.text
    image_rows = _rows(lesson)
    assert image_rows[-1]["embedding_status"] == "ready" and image_rows[-1]["dim"] == 1024
    # A missing image is saved with a visible ingest error, never ready.
    missing = client.post(
        f"/teacher/lessons/{lesson}/slides",
        headers=auth(teacher),
        json={"imageUrl": "/media/missing-integration-image.png", "title": "Missing"},
    )
    assert missing.status_code == 201
    failed = _rows(lesson)[-1]
    assert (
        failed["embedding_status"] == "failed"
        and failed["embedding_error"]
        and failed["dim"] is None
    )
    final = [str(r["id"]) for r in _rows(lesson)]
    assert client.delete(f"/teacher/lessons/{lesson}", headers=auth(teacher)).status_code == 200
    assert asyncio.run(vector_count(final)) == 0
