"""Unit tests for agent.tellus.subagents."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("MINIMAX_API_KEY", "test-key")

from agent.tellus import subagents as tellus_subagents


def test_subagents_list_has_one_entry_in_phase_2():
    assert len(tellus_subagents.SUBAGENTS) == 1


def test_planner_entry_has_required_fields():
    planner = next(s for s in tellus_subagents.SUBAGENTS if s["name"] == "planner")

    for key in ("name", "description", "system_prompt", "model"):
        assert key in planner, f"planner subagent missing key: {key}"


def test_planner_description_guides_delegation():
    planner = next(s for s in tellus_subagents.SUBAGENTS if s["name"] == "planner")
    desc = planner["description"]
    assert "plan" in desc.lower()
    assert "/workspace/plan.md" in desc
    assert len(desc) <= 250


def test_planner_system_prompt_contains_soul_and_skills():
    planner = next(s for s in tellus_subagents.SUBAGENTS if s["name"] == "planner")
    prompt = planner["system_prompt"]

    assert "# Planner — Tellus Open-SWE" in prompt
    assert "# Skill: Plan Writing" in prompt
    assert "# Skill: Coding Pipeline" in prompt
    assert prompt.index("# Planner") < prompt.index("# Skill: Plan Writing")


def test_missing_soul_fails_loudly_at_import(monkeypatch, tmp_path):
    """If planner.md is missing, import should fail loudly."""
    from importlib import reload

    from agent.tellus import souls_loader

    monkeypatch.setattr(souls_loader, "SOULS_DIR", tmp_path)

    with pytest.raises(souls_loader.SoulNotFound):
        reload(tellus_subagents)
