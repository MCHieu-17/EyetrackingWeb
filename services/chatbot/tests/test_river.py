import asyncio
from types import SimpleNamespace
from app.workflow.river import River
from app.workflow.router import RoutePlan


def test_router_never_retries_but_verifier_has_one_transport_retry(monkeypatch):
    class Client:
        def __init__(self):
            self.retries = []
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def with_options(self, **options):
            self.retries.append(options["max_retries"])
            return self

        async def create(self, **kw):
            args = '{"routes":["general"]}'
            call = SimpleNamespace(function=SimpleNamespace(arguments=args))
            message = SimpleNamespace(tool_calls=[call])
            return SimpleNamespace(usage=None, choices=[SimpleNamespace(message=message)])

    river = River()
    original = river.client
    client = Client()
    river.client = client
    monkeypatch.setenv("RIVER_QUEUE_TIMEOUT", "1")
    river.requests_per_second = 1000

    async def run():
        try:
            await river.structured("router", [], RoutePlan)
            assert client.retries == []
            await river.structured("verify", [], RoutePlan)
            assert client.retries == [1]
        finally:
            await original.close()

    asyncio.run(run())
