"""Embedding queue: một model instance, query lane tách khỏi ingest."""

from __future__ import annotations

import threading
import time

import pytest

from app.workflow.embedding_queue import ManagedEmbedding

pytestmark = pytest.mark.fast


class FakeModel:
    query_encode_kwargs = {}

    def _embed(self, texts, kwargs):
        return [[1.0, 0.0] for _ in texts]

    def embed_documents(self, texts):
        time.sleep(0.5)
        return [[0.0, 1.0] for _ in texts]


def test_query_lane_does_not_wait_for_ingest():
    embedding = ManagedEmbedding(FakeModel(), "fake")
    result: dict[str, list[list[float]]] = {}
    try:
        ingest = threading.Thread(
            target=lambda: result.setdefault(
                "vector", embedding.embed_documents(["long document"])
            )
        )
        ingest.start()
        time.sleep(0.05)

        started = time.monotonic()
        vector = embedding.embed_query("question")
        elapsed = time.monotonic() - started

        assert vector == [1.0, 0.0]
        assert elapsed < 0.25, f"query waited {elapsed:.3f}s behind ingest"
        ingest.join(timeout=2)
        assert result["vector"] == [[0.0, 1.0]]
    finally:
        embedding.close()


def test_embedding_factory_shares_one_model(monkeypatch):
    from app.workflow import providers

    class StubEmbedding:
        def __init__(self, model, key):
            self.model = model
            self.key = key

    monkeypatch.setattr(
        "app.workflow.embedding_queue.ManagedEmbedding", StubEmbedding
    )
    monkeypatch.setattr(providers, "_build_embedding", lambda name: name)
    providers._get_embedding.cache_clear()
    try:
        assert providers.get_embedding() is providers.get_embedding("local")
    finally:
        providers._get_embedding.cache_clear()


class BatchModel:
    query_encode_kwargs = {}

    def __init__(self):
        self.batch_sizes: list[int] = []
        self.lock = threading.Lock()

    def embed_documents(self, texts):
        with self.lock:
            self.batch_sizes.append(len(texts))
        time.sleep(0.05)
        return [[0.0, 1.0] for _ in texts]


def test_ingest_lane_coalesces_concurrent_documents():
    model = BatchModel()
    embedding = ManagedEmbedding(model, "fake")
    barrier = threading.Barrier(8)
    results: dict[int, list[list[float]]] = {}
    threads = [
        threading.Thread(
            target=lambda index=index: (
                barrier.wait(),
                results.setdefault(index, embedding.embed_documents([f"doc {index}"])),
            )
        )
        for index in range(8)
    ]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        assert len(results) == 8
        assert sum(model.batch_sizes) == 8
        assert max(model.batch_sizes) >= 8
    finally:
        embedding.close()
