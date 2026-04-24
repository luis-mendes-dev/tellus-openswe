"""SOUL loader.

Loads a Tellus SOUL (markdown system prompt) by name. All SOULs live in
`agent/tellus/souls/<name>.md`. Missing files raise `SoulNotFound` so a
silent empty persona never reaches production.
"""
from __future__ import annotations

from pathlib import Path

SOULS_DIR = Path(__file__).resolve().parent / "souls"


class SoulNotFound(FileNotFoundError):
    """Raised when a requested SOUL markdown file is missing."""


def load_soul(name: str) -> str:
    """Return the markdown content of `agent/tellus/souls/<name>.md`."""
    path = SOULS_DIR / f"{name}.md"
    try:
        content = path.read_text()
    except FileNotFoundError as exc:
        raise SoulNotFound(
            f"SOUL '{name}' not found at {path}. Every registered SOUL must exist on disk."
        ) from exc

    if not content.endswith("\n"):
        content += "\n"
    return content
