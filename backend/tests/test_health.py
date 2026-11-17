import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/health", "/api/health"])
async def test_health(client, path):
    response = await client.get(path)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["schemaGeneration"] == "13"
