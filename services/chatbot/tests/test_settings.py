"""Cấu hình model embedding local phải đặt tường minh, không dùng default."""

import pytest

from app import settings

EMBEDDING_KEYS = [
    "EMBEDDING_NAME",
    "EMBEDDING_DIM",
    "EMBEDDING_MODEL_PATH",
    "EMBEDDING_DEVICE",
    "EMBEDDING_LOCAL_FILES_ONLY",
    "EMBEDDING_HF_REPO",
]


def _set_required_non_embedding(monkeypatch):
    monkeypatch.setenv("CHATBOT_DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("CHATBOT_INTERNAL_TOKEN", "test-token")
    monkeypatch.setenv("NEU_BASE_URL", "http://localhost:8000/v1")
    monkeypatch.setenv("NEU_API_KEY", "test-key")
    for key in (
        "R2_ACCOUNT_ID",
        "R2_BUCKET_NAME",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_PUBLIC_URL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_validate_requires_all_local_embedding_settings(monkeypatch):
    _set_required_non_embedding(monkeypatch)
    for key in EMBEDDING_KEYS:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        settings.validate()

    message = str(exc_info.value)
    for key in EMBEDDING_KEYS:
        assert key in message


def test_validate_rejects_invalid_embedding_device(monkeypatch):
    _set_required_non_embedding(monkeypatch)
    monkeypatch.setenv("EMBEDDING_NAME", "local")
    monkeypatch.setenv("EMBEDDING_DIM", "1024")
    monkeypatch.setenv("EMBEDDING_MODEL_PATH", "/app/weights/model")
    monkeypatch.setenv("EMBEDDING_DEVICE", "gpu")
    monkeypatch.setenv("EMBEDDING_LOCAL_FILES_ONLY", "true")
    monkeypatch.setenv("EMBEDDING_HF_REPO", "org/model")

    with pytest.raises(RuntimeError, match="EMBEDDING_DEVICE"):
        settings.validate()


def test_embedding_device_requires_explicit_value(monkeypatch):
    monkeypatch.delenv("EMBEDDING_DEVICE", raising=False)
    with pytest.raises(RuntimeError, match="EMBEDDING_DEVICE"):
        settings.embedding_device()

    monkeypatch.setenv("EMBEDDING_DEVICE", "cpu")
    assert settings.embedding_device() == "cpu"
