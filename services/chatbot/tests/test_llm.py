"""Tests cho cấu hình transport NEU."""

from app import settings
from app.workflow.llm import LLMClient


def test_neu_headers_uses_custom_header(monkeypatch):
    monkeypatch.setenv("NEU_API_KEY", "research")
    monkeypatch.setenv("NEU_AUTH_HEADER", "x-ollama-seckey")
    monkeypatch.setenv("NEU_AUTH_SCHEME", "")

    assert settings.neu_headers() == {"x-ollama-seckey": "research"}


def test_neu_headers_supports_bearer_scheme(monkeypatch):
    monkeypatch.setenv("NEU_API_KEY", "secret")
    monkeypatch.setenv("NEU_AUTH_HEADER", "Authorization")
    monkeypatch.setenv("NEU_AUTH_SCHEME", "Bearer")

    assert settings.neu_headers() == {"Authorization": "Bearer secret"}


def test_neu_headers_empty_without_key(monkeypatch):
    monkeypatch.setenv("NEU_API_KEY", "")

    assert settings.neu_headers() == {}


def test_neu_vlm_model_falls_back_to_llm_model(monkeypatch):
    monkeypatch.setenv("NEU_LLM_MODEL", "qwen3.5-35b-a3b-int4")
    monkeypatch.setenv("NEU_VLM_MODEL", "")

    assert settings.neu_vlm_model() == "qwen3.5-35b-a3b-int4"


def test_llm_options_disable_thinking(monkeypatch):
    monkeypatch.setenv("NEU_LLM_MODEL", "qwen3.5-35b-a3b-int4")
    monkeypatch.setenv("NEU_ENABLE_THINKING", "false")
    monkeypatch.setenv("NEU_QUERY_MAX_TOKENS", "400")
    monkeypatch.setenv("ANSWER_MAX_TOKENS", "2048")
    monkeypatch.setenv("ANSWER_TEMPERATURE", "0.2")

    client = LLMClient.__new__(LLMClient)
    options = client.options("query")

    assert options["model"] == "qwen3.5-35b-a3b-int4"
    assert options["max_tokens"] == 400
    assert options["extra_body"] == {
        "chat_template_kwargs": {"enable_thinking": False}
    }
    assert "reasoning_effort" not in options
    assert "reasoning_effort" not in options["extra_body"]
