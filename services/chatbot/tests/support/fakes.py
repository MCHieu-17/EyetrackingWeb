"""Fake VLM/embedding/LLM ở biên provider."""

from __future__ import annotations

import threading
from types import SimpleNamespace

from langchain_core.runnables import RunnableLambda


class FakeEmbeddings:
    """Vector 1024 chiều xác định theo từ khóa để test retrieval."""

    def __init__(self):
        self.documents: list[list[str]] = []
        self.queries: list[str] = []

    @staticmethod
    def vector(text: str) -> list[float]:
        vector = [0.0] * 1024
        lowered = (text or "").lower()
        if "alpha" in lowered:
            vector[0] = 1.0
        elif "beta" in lowered:
            vector[1] = 1.0
        else:
            vector[2] = 1.0
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.documents.append(list(texts))
        return [self.vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return self.vector(text)

    async def aembed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return self.vector(text)

    def close(self):
        return None


class FakeVLM:
    """Trả transcript cố định; có thể lỗi theo số lần gọi."""

    def __init__(self, transcript: str = "Nội dung slide alpha"):
        self.transcript = transcript
        self.calls = 0
        self.fail_first = False
        self.fail_all = False
        self._lock = threading.Lock()

    def with_structured_output(self, *args, **kwargs):
        return RunnableLambda(self._invoke)

    def _invoke(self, payload):
        with self._lock:
            self.calls += 1
            call = self.calls
        if self.fail_all or (self.fail_first and call == 1):
            from app.services.ingest import VLMUnavailableError

            raise VLMUnavailableError("VLM tạm thời không khả dụng")
        return SimpleNamespace(transcript=self.transcript)


class FakeLLM:
    def __init__(self):
        self.query = "alpha"
        self.hyde = ""
        self.chunks: list[str] = ["Câu trả lời [1]."]
        self.chunks_by_call: dict[int, list[str]] = {}
        self.stream_calls = 0
        self.structured_calls = 0

    async def structured(self, purpose, prompt, schema):
        self.structured_calls += 1
        data = {"query": self.query, "hypothetical_answer": self.hyde}
        return schema.model_validate(data)

    async def stream(self, prompt):
        self.stream_calls += 1
        chunks = self.chunks_by_call.get(self.stream_calls, self.chunks)
        for chunk in chunks:
            yield chunk

    async def close(self):
        return None
