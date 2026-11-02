import pytest


@pytest.fixture(autouse=True)
def _base_env(monkeypatch):
    """Env tối thiểu để settings.validate() pass; test nào cần thiếu thì delenv."""
    monkeypatch.setenv(
        "CHATBOT_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/eyetracking_test",
    )
    monkeypatch.setenv("CHATBOT_INTERNAL_TOKEN", "test-token")
    monkeypatch.setenv("RIVER_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_NAME", "local")
    monkeypatch.setenv("EMBEDDING_DIM", "1024")
    monkeypatch.setenv("RAG_TOP_K", "8")
    monkeypatch.setenv("RAG_CANDIDATES", "20")
    monkeypatch.setenv("RAG_RRF_K", "60")
    monkeypatch.setenv("RAG_SCORE_THRESHOLD", "0.25")
    monkeypatch.setenv("CITATION_MAX_ATTEMPTS", "2")
