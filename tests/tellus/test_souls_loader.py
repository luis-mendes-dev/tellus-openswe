"""Unit tests for agent.tellus.souls_loader."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent.tellus import souls_loader


def test_load_soul_returns_file_contents(monkeypatch):
    fixture_dir = Path(__file__).parent / "fixtures" / "souls"
    monkeypatch.setattr(souls_loader, "SOULS_DIR", fixture_dir)

    content = souls_loader.load_soul("minimal")

    assert "tellus minimal test persona" in content
    assert content.endswith("\n")  # preserve trailing newline so concat is clean


def test_load_soul_raises_on_missing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(souls_loader, "SOULS_DIR", tmp_path)

    with pytest.raises(souls_loader.SoulNotFound) as excinfo:
        souls_loader.load_soul("does_not_exist")

    assert "does_not_exist" in str(excinfo.value)


def test_soul_not_found_is_a_file_not_found_subclass():
    """So callers that already catch FileNotFoundError still work."""
    assert issubclass(souls_loader.SoulNotFound, FileNotFoundError)
