"""Unit tests for agent.tellus.skill_loader."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent.tellus import skill_loader


@pytest.fixture
def fixture_skills(monkeypatch):
    fixture_dir = Path(__file__).parent / "fixtures" / "skills"
    monkeypatch.setattr(skill_loader, "SKILLS_DIR", fixture_dir)
    monkeypatch.setattr(
        skill_loader,
        "ROLE_SKILLS",
        {"planner": ["alpha", "beta"], "implementer": ["alpha"]},
    )
    return fixture_dir


def test_load_skills_for_returns_concatenated_markdown(fixture_skills):
    bundle = skill_loader.load_skills_for("planner")

    assert "Alpha skill" in bundle
    assert "Beta skill" in bundle
    assert bundle.index("Alpha skill") < bundle.index("Beta skill")
    assert "\n\n# Beta skill" in bundle


def test_load_skills_for_unknown_role_returns_empty_string(fixture_skills):
    assert skill_loader.load_skills_for("unknown_role") == ""


def test_load_skills_for_missing_skill_file_raises(fixture_skills, monkeypatch):
    monkeypatch.setattr(
        skill_loader, "ROLE_SKILLS", {"planner": ["alpha", "missing_one"]}
    )
    with pytest.raises(skill_loader.SkillNotFound) as excinfo:
        skill_loader.load_skills_for("planner")
    assert "missing_one" in str(excinfo.value)


def test_skill_not_found_is_a_file_not_found_subclass():
    assert issubclass(skill_loader.SkillNotFound, FileNotFoundError)
