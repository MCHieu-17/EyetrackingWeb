"""Tests cho cấu hình transport LLM/VLM."""

from app import settings
from app.workflow.llm import LLMClient


def test_llm_headers_uses_custom_header(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "research")
    monkeypatch.setenv("LLM_AUTH_HEADER", "x-ollama-seckey")
    monkeypatch.setenv("LLM_AUTH_SCHEME", "")

    assert settings.llm_headers() == {"x-ollama-seckey": "research"}


def test_llm_headers_supports_bearer_scheme(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_AUTH_HEADER", "Authorization")
    monkeypatch.setenv("LLM_AUTH_SCHEME", "Bearer")

    assert settings.llm_headers() == {"Authorization": "Bearer secret"}


def test_llm_headers_defaults_to_bearer(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.delenv("LLM_AUTH_HEADER", raising=False)
    monkeypatch.delenv("LLM_AUTH_SCHEME", raising=False)

    assert settings.llm_headers() == {"Authorization": "Bearer secret"}


def test_llm_headers_empty_without_key(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "")

    assert settings.llm_headers() == {}


def test_vlm_model_falls_back_to_llm_model(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "qwen3.5-35b-a3b-int4")
    monkeypatch.setenv("VLM_MODEL", "")

    assert settings.vlm_model() == "qwen3.5-35b-a3b-int4"


def test_llm_options_disable_thinking(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "qwen3.5-35b-a3b-int4")
    monkeypatch.setenv("LLM_ENABLE_THINKING", "false")
    monkeypatch.setenv("LLM_QUERY_MAX_TOKENS", "400")
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
