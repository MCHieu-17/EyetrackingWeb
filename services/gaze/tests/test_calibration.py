"""Tests cho calibration model .ubj không dùng pickle."""

import pytest

from app.services.calibration import Calibration


def test_fit_predict_and_serialize_roundtrip():
    samples = [
        (0.0, 0.0, 0.25, 0.5),
        (1.0, 0.0, 0.75, 0.5),
        (0.0, 1.0, 0.25, 0.8),
        (1.0, 1.0, 0.75, 0.8),
    ]
    cal = Calibration()
    cal.fit(
        [(pitch, yaw) for pitch, yaw, _, _ in samples],
        [(x, y) for _, _, x, y in samples],
    )
    x, y = cal.predict(0.5, 0.5)
    assert x == pytest.approx(0.5)
    assert y == pytest.approx(0.65)

    restored = Calibration()
    restored.deserialize(cal.serialize())
    assert restored.predict(0.2, 0.9) == pytest.approx(cal.predict(0.2, 0.9))


@pytest.mark.parametrize("data", [b"", b"not-ubjson", b"\x00\x01"])
def test_deserialize_rejects_invalid_payload(data):
    with pytest.raises(ValueError):
        Calibration().deserialize(data)


def test_deserialize_rejects_wrong_shape_and_non_finite_values():
    cal = Calibration()
    with pytest.raises(ValueError):
        cal.deserialize(
            __import__("ubjson").dumpb(
                {"format": "gaze-lr-v2", "coef": [[1, 2]], "intercept": [0, 0]}
            )
        )
    with pytest.raises(ValueError):
        cal.deserialize(
            __import__("ubjson").dumpb(
                {
                    "format": "gaze-lr-v2",
                    "coef": [[float("nan"), 0], [0, 1]],
                    "intercept": [0, 0],
                }
            )
        )


def test_deserialize_rejects_old_format():
    data = __import__("ubjson").dumpb(
        {"format": "gaze-lr-v1", "coef": [[1, 0], [0, 1]], "intercept": [0, 0]}
    )
    with pytest.raises(ValueError):
        Calibration().deserialize(data)


def test_predict_before_fit_raises():
    with pytest.raises(RuntimeError):
        Calibration().predict(0.1, 0.2)
