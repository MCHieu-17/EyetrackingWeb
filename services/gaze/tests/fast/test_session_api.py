"""Hợp đồng session/calibrate/train/model/import."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.fast

POINTS = [
    {"id": "p00", "x": 0.1, "y": 0.2},
    {"id": "p10", "x": 0.9, "y": 0.2},
    {"id": "p01", "x": 0.1, "y": 0.8},
    {"id": "p11", "x": 0.9, "y": 0.8},
]


def _session(client, points=None):
    response = client.post("/session", json={"points": points or POINTS})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def _calibrate(client, sid, point_id, data=b"p00"):
    return client.post(
        f"/session/{sid}/calibrate",
        files={"image": ("face.jpg", data, "image/jpeg")},
        data={"point_id": point_id},
    )


def _trained_session(client, points=None):
    sid = _session(client, points)
    for point in points or POINTS:
        response = _calibrate(client, sid, point["id"], point["id"].encode())
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "accepted"
    trained = client.post(f"/session/{sid}/train")
    assert trained.status_code == 200, trained.text
    return sid


def test_create_status_and_delete_session(client):
    sid = _session(client, POINTS[:1])
    status = client.get(f"/session/{sid}")
    assert status.status_code == 200
    assert status.json() == {"state": "collecting", "calibrated": False}

    deleted = client.delete(f"/session/{sid}")
    assert deleted.status_code == 200
    assert deleted.json() == {"status": "deleted"}
    assert client.get(f"/session/{sid}").status_code == 404
    assert client.delete(f"/session/{sid}").status_code == 404


@pytest.mark.parametrize(
    "points",
    [
        [],
        [{"id": "a", "x": 0.1, "y": 0.2}, {"id": "a", "x": 0.3, "y": 0.4}],
        [{"id": "a", "x": -0.1, "y": 0.2}],
        [{"id": "a", "x": 0.1, "y": 1.2}],
    ],
)
def test_create_session_validation(client, points):
    response = client.post("/session", json={"points": points})
    assert response.status_code == 422


def test_max_points_validation(client):
    points = [{"id": f"p{i}", "x": 0.5, "y": 0.5} for i in range(65)]
    assert client.post("/session", json={"points": points}).status_code == 422


def test_calibrate_unknown_point_and_invalid_images(client):
    sid = _session(client)
    unknown = _calibrate(client, sid, "missing")
    assert unknown.status_code == 200
    assert unknown.json()["status"] == "unknown_point"

    no_face = _calibrate(client, sid, "p00", b"noface")
    assert no_face.status_code == 200
    assert no_face.json()["status"] == "no_face"

    invalid = _calibrate(client, sid, "p00", b"bad")
    assert invalid.status_code == 200
    assert invalid.json()["status"] == "invalid_image"


def test_train_requires_samples(client):
    sid = _session(client, POINTS[:2])
    response = client.post(f"/session/{sid}/train")
    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "insufficient_samples"
    assert body["detail"] == {"p00": 0, "p10": 0}


def test_train_model_and_import_roundtrip(client):
    sid = _trained_session(client)
    status = client.get(f"/session/{sid}")
    assert status.json()["state"] == "ready"
    assert status.json()["calibrated"] is True

    model = client.get(f"/session/{sid}/model")
    assert model.status_code == 200
    assert model.headers["content-type"] == "application/octet-stream"
    assert "calibration_" in model.headers["content-disposition"]

    target = _session(client, POINTS[:1])
    imported = client.post(
        f"/session/{target}/import",
        files={"model": ("model.ubj", model.content, "application/octet-stream")},
    )
    assert imported.status_code == 200
    assert imported.json() == {"status": "ready"}
    assert client.get(f"/session/{target}").json()["calibrated"] is True


def test_model_before_train_and_invalid_import(client):
    sid = _session(client, POINTS[:1])
    assert client.get(f"/session/{sid}/model").status_code == 409

    invalid = client.post(
        f"/session/{sid}/import",
        files={"model": ("bad.ubj", b"not-a-model", "application/octet-stream")},
    )
    assert invalid.status_code == 200
    assert invalid.json() == {"status": "invalid_model"}
