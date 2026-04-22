"""Tests for agent.utils.messages content extraction helpers."""

from __future__ import annotations

from agent.utils.messages import extract_text_content


def test_extract_text_content_from_plain_string() -> None:
    assert extract_text_content("hello world") == "hello world"


def test_extract_text_content_strips_whitespace() -> None:
    assert extract_text_content("   hello   ") == "hello"


def test_extract_text_content_from_openai_blocks() -> None:
    blocks = [
        {"type": "text", "text": "first "},
        {"type": "text", "text": "second"},
    ]
    assert extract_text_content(blocks) == "first second"


def test_extract_text_content_ignores_non_text_blocks() -> None:
    blocks = [
        {"type": "text", "text": "hello"},
        {"type": "image_url", "image_url": {"url": "https://example.com/x.png"}},
        {"type": "text", "text": " world"},
    ]
    assert extract_text_content(blocks) == "hello world"


def test_extract_text_content_returns_empty_for_empty_list() -> None:
    assert extract_text_content([]) == ""


def test_extract_text_content_returns_empty_for_unexpected_type() -> None:
    assert extract_text_content(None) == ""  # type: ignore[arg-type]
    assert extract_text_content(123) == ""  # type: ignore[arg-type]


def test_extract_text_content_handles_block_without_text_key() -> None:
    blocks = [
        {"type": "text"},
        {"type": "text", "text": "only"},
    ]
    assert extract_text_content(blocks) == "only"


def test_extract_text_content_empty_string_returns_empty() -> None:
    assert extract_text_content("") == ""


def test_extract_text_content_string_with_only_whitespace() -> None:
    assert extract_text_content("   \n\t ") == ""
