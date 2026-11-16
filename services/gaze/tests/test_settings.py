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
