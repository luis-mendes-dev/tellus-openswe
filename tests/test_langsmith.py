"""Tests for agent.utils.langsmith trace URL helpers."""

from __future__ import annotations

import pytest

from agent.utils.langsmith import get_langsmith_trace_url


def test_get_langsmith_trace_url_builds_full_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_URL_PROD", "https://smith.langchain.com")
    monkeypatch.setenv("LANGSMITH_TENANT_ID_PROD", "tenant-abc")
    monkeypatch.setenv("LANGSMITH_TRACING_PROJECT_ID_PROD", "project-xyz")

    url = get_langsmith_trace_url("run-123")

    assert url == (
        "https://smith.langchain.com/o/tenant-abc/projects/p/project-xyz"
        "?peek=run-123&peeked_trace=run-123"
    )


def test_get_langsmith_trace_url_uses_default_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGSMITH_URL_PROD", raising=False)
    monkeypatch.setenv("LANGSMITH_TENANT_ID_PROD", "t1")
    monkeypatch.setenv("LANGSMITH_TRACING_PROJECT_ID_PROD", "p1")

    url = get_langsmith_trace_url("run-abc")

    assert url is not None
    assert url.startswith("https://smith.langchain.com/o/t1/projects/p/p1")


def test_get_langsmith_trace_url_returns_none_when_tenant_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LANGSMITH_TENANT_ID_PROD", raising=False)
    monkeypatch.setenv("LANGSMITH_TRACING_PROJECT_ID_PROD", "project-xyz")

    assert get_langsmith_trace_url("run-1") is None


def test_get_langsmith_trace_url_returns_none_when_project_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGSMITH_TENANT_ID_PROD", "tenant-abc")
    monkeypatch.delenv("LANGSMITH_TRACING_PROJECT_ID_PROD", raising=False)

    assert get_langsmith_trace_url("run-1") is None


def test_get_langsmith_trace_url_respects_custom_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_URL_PROD", "https://custom.example.com")
    monkeypatch.setenv("LANGSMITH_TENANT_ID_PROD", "t1")
    monkeypatch.setenv("LANGSMITH_TRACING_PROJECT_ID_PROD", "p1")

    url = get_langsmith_trace_url("run-xyz")

    assert url is not None
    assert url.startswith("https://custom.example.com/o/t1/projects/p/p1")
    assert url.endswith("?peek=run-xyz&peeked_trace=run-xyz")
