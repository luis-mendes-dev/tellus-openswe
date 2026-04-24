"""Tellus subagent registry.

Phase 2 registers exactly one subagent - the planner. Later phases extend
this list with implementer, QA trio, fixer, and others.
"""
from __future__ import annotations

from deepagents.middleware.subagents import SubAgent

from agent.tellus.models import make_model
from agent.tellus.skill_loader import load_skills_for
from agent.tellus.souls_loader import load_soul

_SOUL_SKILL_SEPARATOR = "\n---\n"


def _build_system_prompt(soul_name: str, role: str) -> str:
    soul = load_soul(soul_name).rstrip()
    skills = load_skills_for(role).rstrip()
    if not skills:
        return soul + "\n"
    return f"{soul}{_SOUL_SKILL_SEPARATOR}{skills}\n"


SUBAGENTS: list[SubAgent] = [
    {
        "name": "planner",
        "description": (
            "Produces an implementation plan at /workspace/plan.md for the "
            "current ticket. Returns a five-line summary. Does not write "
            "source code, run tests, or open PRs."
        ),
        "system_prompt": _build_system_prompt("planner", "planner"),
        "model": make_model("planner"),
    },
]
