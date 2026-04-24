"""Unit tests for agent.tellus.models."""
from __future__ import annotations

from unittest import mock

import pytest

from agent.tellus import models as tellus_models


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Isolate every test from host env."""
    for key in (
        "MINIMAX_API_KEY",
        "MINIMAX_BASE_URL",
        "OPENAI_API_KEY",
        "LLM_MODEL_ID",
    ):
        monkeypatch.delenv(key, raising=False)
    yield


def test_minimax_prefix_routes_to_openai_provider_with_minimax_base_url(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    captured: dict = {}

    def fake_init_chat_model(model, **kwargs):
        captured["model"] = model
        captured["kwargs"] = kwargs
        return mock.sentinel.chat_model

    monkeypatch.setattr(tellus_models, "init_chat_model", fake_init_chat_model)

    result = tellus_models.make_model("minimax:MiniMax-M1", max_tokens=1234)

    assert result is mock.sentinel.chat_model
    assert captured["model"] == "openai:MiniMax-M1"
    assert captured["kwargs"]["base_url"] == "https://api.minimax.io/v1"
    assert captured["kwargs"]["api_key"] == "test-key"
    assert captured["kwargs"]["max_tokens"] == 1234
    # minimax OpenAI-compatible endpoint is chat-completions, not Responses API
    assert "use_responses_api" not in captured["kwargs"]


def test_minimax_prefix_requires_api_key(monkeypatch):
    with pytest.raises(KeyError):
        tellus_models.make_model("minimax:MiniMax-M1")


def test_minimax_base_url_env_override(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    monkeypatch.setenv("MINIMAX_BASE_URL", "https://minimax.internal/v1")

    captured: dict = {}

    def fake_init_chat_model(model, **kwargs):
        captured["kwargs"] = kwargs
        return mock.sentinel.chat_model

    monkeypatch.setattr(tellus_models, "init_chat_model", fake_init_chat_model)

    tellus_models.make_model("minimax:MiniMax-M1")

    assert captured["kwargs"]["base_url"] == "https://minimax.internal/v1"


def test_non_minimax_prefix_falls_through_to_upstream(monkeypatch):
    """Anthropic and plain openai prefixes must delegate to upstream make_model."""
    called_with: dict = {}

    def fake_upstream(model_id, **kwargs):
        called_with["model_id"] = model_id
        called_with["kwargs"] = kwargs
        return mock.sentinel.upstream_model

    monkeypatch.setattr(tellus_models, "_upstream_make_model", fake_upstream)

    result = tellus_models.make_model("anthropic:claude-opus-4-6", max_tokens=500)

    assert result is mock.sentinel.upstream_model
    assert called_with["model_id"] == "anthropic:claude-opus-4-6"
    assert called_with["kwargs"] == {"max_tokens": 500}


def test_defaults_to_llm_model_id_env(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL_ID", "minimax:MiniMax-M1")

    captured: dict = {}

    def fake_init_chat_model(model, **kwargs):
        captured["model"] = model
        return mock.sentinel.chat_model

    monkeypatch.setattr(tellus_models, "init_chat_model", fake_init_chat_model)

    tellus_models.make_model()  # no model_id arg

    assert captured["model"] == "openai:MiniMax-M1"
