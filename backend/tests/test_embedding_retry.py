import asyncio

import httpx
import pytest

from app.services import embedding


@pytest.mark.parametrize(
    "statuses, expected", [([429, 503, 200], 3), ([400], 1), ([429, 429, 429], 3)]
)
def test_ingest_retry_is_bounded(monkeypatch, statuses, expected):
    calls = []

    async def handle(request):
        code = statuses[len(calls)]
        calls.append(request)
        return httpx.Response(code, json={"processed": 1})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        embedding.httpx,
        "AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handle), **kw),
    )
    monkeypatch.setattr(embedding.settings, "chatbot_ingest_attempts", 3)
    monkeypatch.setattr(embedding.settings, "chatbot_ingest_backoff_seconds", 0)
    if statuses[-1] == 200:
        assert asyncio.run(embedding._call("/ingest/slide", {})) == {"processed": 1}
    else:
        with pytest.raises(RuntimeError):
            asyncio.run(embedding._call("/ingest/slide", {}))
    assert len(calls) == expected


def test_ingest_retries_timeouts_and_succeeds(monkeypatch):
    count = 0

    async def handle(request):
        nonlocal count
        count += 1
        if count < 3:
            raise httpx.ReadTimeout("test timeout", request=request)
        return httpx.Response(200, json={"processed": 1})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        embedding.httpx,
        "AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handle), **kw),
    )
    monkeypatch.setattr(embedding.settings, "chatbot_ingest_attempts", 3)
    monkeypatch.setattr(embedding.settings, "chatbot_ingest_backoff_seconds", 0)
    assert asyncio.run(embedding._call("/ingest/slide", {}))["processed"] == 1
    assert count == 3
