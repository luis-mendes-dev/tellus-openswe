"""Unit tests for agent.tellus.prompt.construct_system_prompt."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent.tellus import prompt as tellus_prompt
from agent.tellus import souls_loader


@pytest.fixture
def fixture_souls(monkeypatch):
    fixture_dir = Path(__file__).parent / "fixtures" / "souls"
    monkeypatch.setattr(souls_loader, "SOULS_DIR", fixture_dir)
    return fixture_dir


def test_prompt_starts_with_soul_then_separator_then_upstream(fixture_souls, monkeypatch):
    monkeypatch.setattr(tellus_prompt, "TELLUS_SOUL_NAME", "minimal")

    def fake_upstream(working_dir, linear_project_id="", linear_issue_number=""):
        return f"UPSTREAM[{working_dir}|{linear_project_id}|{linear_issue_number}]"

    monkeypatch.setattr(tellus_prompt, "_upstream_construct_system_prompt", fake_upstream)

    rendered = tellus_prompt.construct_system_prompt(
        working_dir="/sbx",
        linear_project_id="TEL",
        linear_issue_number="42",
    )

    assert rendered.startswith("# Minimal Test SOUL"), rendered[:200]
    assert "UPSTREAM[/sbx|TEL|42]" in rendered
    soul_end = rendered.index("UPSTREAM[")
    soul_slice = rendered[:soul_end]
    # separator must appear exactly once, between SOUL and upstream block
    assert soul_slice.count("\n---\n") == 1


def test_prompt_passes_empty_linear_fields_through(fixture_souls, monkeypatch):
    monkeypatch.setattr(tellus_prompt, "TELLUS_SOUL_NAME", "minimal")

    captured: dict = {}

    def fake_upstream(working_dir, linear_project_id="", linear_issue_number=""):
        captured["args"] = (working_dir, linear_project_id, linear_issue_number)
        return "UPSTREAM"

    monkeypatch.setattr(tellus_prompt, "_upstream_construct_system_prompt", fake_upstream)

    tellus_prompt.construct_system_prompt(working_dir="/sbx")

    assert captured["args"] == ("/sbx", "", "")


def test_prompt_raises_if_squad_lead_soul_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(souls_loader, "SOULS_DIR", tmp_path)
    monkeypatch.setattr(tellus_prompt, "TELLUS_SOUL_NAME", "does_not_exist")

    with pytest.raises(souls_loader.SoulNotFound):
        tellus_prompt.construct_system_prompt(working_dir="/sbx")


def test_prompt_signature_matches_upstream():
    """Signature parity is what lets server.py do a single-line import swap."""
    import inspect

    from agent.prompt import construct_system_prompt as upstream

    upstream_sig = inspect.signature(upstream)
    tellus_sig = inspect.signature(tellus_prompt.construct_system_prompt)

    assert list(tellus_sig.parameters) == list(upstream_sig.parameters)
    for name, upstream_param in upstream_sig.parameters.items():
        tellus_param = tellus_sig.parameters[name]
        assert tellus_param.default == upstream_param.default, name
