"""Tellus system-prompt composer.

Prepends the Tellus squad-lead SOUL to the upstream Open-SWE system prompt.
Signature is identical to `agent.prompt.construct_system_prompt` so the only
change in `agent/server.py` is an import swap.
"""
from __future__ import annotations

from agent.prompt import construct_system_prompt as _upstream_construct_system_prompt
from agent.tellus.souls_loader import load_soul

TELLUS_SOUL_NAME = "squad_lead"

_SEPARATOR = "\n---\n"


def construct_system_prompt(
    working_dir: str,
    linear_project_id: str = "",
    linear_issue_number: str = "",
) -> str:
    """Return the Tellus-augmented system prompt."""
    soul = load_soul(TELLUS_SOUL_NAME).rstrip() + "\n"
    upstream = _upstream_construct_system_prompt(
        working_dir=working_dir,
        linear_project_id=linear_project_id,
        linear_issue_number=linear_issue_number,
    )
    return f"{soul}{_SEPARATOR}{upstream}"
