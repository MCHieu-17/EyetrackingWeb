"""Model local phải được đặt tường minh trong .env/stack.env."""

import pytest

from app import settings


def test_get_device_requires_explicit_valid_value(monkeypatch):
    monkeypatch.setattr(settings, "DEVICE", "")
    with pytest.raises(RuntimeError, match="DEVICE"):
        settings.get_device()

    monkeypatch.setattr(settings, "DEVICE", "gpu")
    with pytest.raises(RuntimeError, match="DEVICE"):
        settings.get_device()

    monkeypatch.setattr(settings, "DEVICE", "cpu")
    assert settings.get_device() == "cpu"


def test_get_unigaze_model_requires_explicit_name(monkeypatch):
    monkeypatch.setattr(settings, "UNIGAZE_MODEL", "")
    with pytest.raises(RuntimeError, match="UNIGAZE_MODEL"):
        settings.get_unigaze_model()

    monkeypatch.setattr(settings, "UNIGAZE_MODEL", "../model")
    with pytest.raises(RuntimeError, match="không hợp lệ"):
        settings.get_unigaze_model()

    monkeypatch.setattr(settings, "UNIGAZE_MODEL", "unigaze_b16_joint")
    assert settings.get_unigaze_model() == "unigaze_b16_joint"


def test_unigaze_weights_path_follows_env(monkeypatch):
    monkeypatch.setattr(settings, "UNIGAZE_MODEL", "unigaze_l16_joint")
    assert settings.unigaze_weights_path() == (
        settings.WEIGHTS_DIR / "unigaze_l16_joint.safetensors"
    )


@pytest.mark.parametrize(
    ("fps", "expected"),
    [(12, 79), (15, 63), (1, 950), (60, 15)],
)
def test_frame_interval_ms_from_fps(fps, expected):
    assert settings.frame_interval_ms(fps) == expected


@pytest.mark.parametrize("fps", [0, 61])
def test_frame_interval_ms_rejects_out_of_range(fps):
    with pytest.raises(ValueError, match="1..60"):
        settings.frame_interval_ms(fps)
