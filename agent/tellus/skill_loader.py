"""Skill loader.

Maps a subagent role to a list of skill names; returns the concatenated
markdown content of those skills ready for appending to a subagent's
`system_prompt`. Unknown roles return the empty string (no skills injected).
Missing skill files raise `SkillNotFound` so typos in `ROLE_SKILLS` fail
loud at registration time.
"""
from __future__ import annotations

from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent / "skills"

# Role -> ordered list of skill names (file stems under SKILLS_DIR).
# Phase 2 covers the planner only; later phases extend this map.
ROLE_SKILLS: dict[str, list[str]] = {
    "planner": ["plan_writing", "coding_pipeline"],
}


class SkillNotFound(FileNotFoundError):
    """Raised when a skill file referenced in ROLE_SKILLS is missing."""


def load_skills_for(role: str) -> str:
    """Return concatenated skill markdown for a role, or empty if unknown."""
    skill_names = ROLE_SKILLS.get(role)
    if not skill_names:
        return ""

    parts: list[str] = []
    for name in skill_names:
        path = SKILLS_DIR / f"{name}.md"
        try:
            parts.append(path.read_text().rstrip())
        except FileNotFoundError as exc:
            raise SkillNotFound(
                f"Skill '{name}' not found at {path}. "
                f"Referenced by ROLE_SKILLS[{role!r}]."
            ) from exc

    return "\n\n".join(parts) + "\n"
