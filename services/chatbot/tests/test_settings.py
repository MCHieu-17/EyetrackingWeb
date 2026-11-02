import pytest

from app import settings


def test_validate_ok():
    settings.validate()


def test_validate_missing_database(monkeypatch):
    monkeypatch.delenv("CHATBOT_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL_DOCKER", raising=False)
    with pytest.raises(RuntimeError, match="CHATBOT_DATABASE_URL"):
        settings.validate()


def test_validate_missing_token(monkeypatch):
    monkeypatch.delenv("CHATBOT_INTERNAL_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="CHATBOT_INTERNAL_TOKEN"):
        settings.validate()


def test_validate_missing_river_key(monkeypatch):
    monkeypatch.delenv("RIVER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="RIVER_API_KEY"):
        settings.validate()


def test_database_url_strips_asyncpg(monkeypatch):
    monkeypatch.setenv(
        "CHATBOT_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/db",
    )
    assert settings.database_url().startswith("postgresql://")


def test_embedding_dim_default():
    assert settings.embedding_dim() == 1024
