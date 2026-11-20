"""Health/ready contract với runtime thật + stage giả."""

import pytest

pytestmark = pytest.mark.fast


def test_health_reports_pipeline_and_sessions(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["pipeline_ready"] is True
    assert body["device"] == "cpu"
    assert body["model"] == "fake-unigaze"
    assert body["precision"] == "fp32"
    assert set(body["queue"]) == {"cpu", "gpu"}
    assert "stats" in body
    assert set(body["sessions"]) == {"total", "ready"}


def test_ready_returns_503_when_pipeline_closed(client, gaze_runtime):
    gaze_runtime.close()
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["pipeline_ready"] is False
