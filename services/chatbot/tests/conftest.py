"""Fixture chatbot: PostgreSQL thật, VLM/embedding/LLM giả."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager

os.environ.setdefault("CHATBOT_INTERNAL_TOKEN", "test-internal-token")
os.environ.setdefault("EMBEDDING_NAME", "local")
os.environ.setdefault("EMBEDDING_DIM", "1024")
os.environ.setdefault("EMBEDDING_MODEL_PATH", "/tmp/no-model")
os.environ.setdefault("EMBEDDING_DEVICE", "cpu")
os.environ.setdefault("EMBEDDING_LOCAL_FILES_ONLY", "true")
os.environ.setdefault("EMBEDDING_HF_REPO", "test/model")
os.environ.setdefault("LLM_BASE_URL", "http://llm.invalid/v1")
os.environ.setdefault("LLM_API_KEY", "test")
os.environ.setdefault("LLM_MODEL", "test-model")
os.environ.setdefault("LLM_MAX_RETRIES", "0")

from app.main import app  # noqa: E402
from app.settings import database_url  # noqa: E402
from tests.support import fakes  # noqa: E402
from tests.support.db import truncate_all  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db(request):
    # Smoke chạy trên DB thật với role read-only; tuyệt đối không truncate.
    if request.node.get_closest_marker("smoke"):
        yield
        return

    from app.api.ingest import close_ingestion
    from app.workflow.lms import backend_client
    from app.workflow.query import clear_query_cache
    from app.workflow.retrieval import close_retriever

    backend_client.cache_clear()
    clear_query_cache()
    close_ingestion()
    close_retriever()
    truncate_all()
    yield
    clear_query_cache()
    close_ingestion()
    close_retriever()
    truncate_all()


@pytest.fixture
def fake_providers(monkeypatch):
    embedding = fakes.FakeEmbeddings()
    vlm = fakes.FakeVLM()
    llm = fakes.FakeLLM()

    monkeypatch.setattr("app.main.get_embedding", lambda *a, **k: embedding)
    monkeypatch.setattr("app.services.ingest.get_embedding", lambda *a, **k: embedding)
    monkeypatch.setattr("app.services.ingest.get_vlm", lambda: vlm)
    monkeypatch.setattr("app.workflow.retrieval.get_embedding", lambda *a, **k: embedding)
    monkeypatch.setattr("app.workflow.query.get_llm_client", lambda: llm)
    monkeypatch.setattr("app.workflow.generation.get_llm_client", lambda: llm)
    monkeypatch.setattr("app.workflow.llm.get_llm_client", lambda: llm)

    class Bundle:
        def __init__(self):
            self.embedding = embedding
            self.vlm = vlm
            self.llm = llm

    return Bundle()


@pytest_asyncio.fixture
async def client(fake_providers) -> AsyncIterator[httpx.AsyncClient]:
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as http:
            http.headers["X-Chatbot-Token"] = "test-internal-token"
            yield http


@pytest.fixture
def db_url() -> str:
    return database_url()
