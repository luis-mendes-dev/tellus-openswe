from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx

from agent.utils.multimodal import extract_image_urls, fetch_slack_text_files


def test_extract_image_urls_empty() -> None:
    assert extract_image_urls("") == []


def test_extract_image_urls_markdown_and_direct_dedupes() -> None:
    text = (
        "Here is an image ![alt](https://example.com/a.png) and another "
        "![https://example.com/b.JPG?size=large plus a repeat https://example.com/a.png"
    )

    assert extract_image_urls(text) == [
        "https://example.com/a.png",
        "https://example.com/b.JPG?size=large",
    ]


def test_extract_image_urls_ignores_non_images() -> None:
    text = "Not images: https://example.com/file.pdf and https://example.com/noext"

    assert extract_image_urls(text) == []


def test_extract_image_urls_markdown_syntax() -> None:
    text = "Check out this screenshot: ![Screenshot](https://example.com/screenshot.png)"

    assert extract_image_urls(text) == ["https://example.com/screenshot.png"]


def test_extract_image_urls_direct_links() -> None:
    text = "Direct link: https://example.com/photo.jpg and another https://example.com/image.gif"

    assert extract_image_urls(text) == [
        "https://example.com/photo.jpg",
        "https://example.com/image.gif",
    ]


def test_extract_image_urls_various_formats() -> None:
    text = (
        "Multiple formats: "
        "https://example.com/image.png "
        "https://example.com/photo.jpeg "
        "https://example.com/pic.gif "
        "https://example.com/img.webp "
        "https://example.com/bitmap.bmp "
        "https://example.com/scan.tiff"
    )

    assert extract_image_urls(text) == [
        "https://example.com/image.png",
        "https://example.com/photo.jpeg",
        "https://example.com/pic.gif",
        "https://example.com/img.webp",
        "https://example.com/bitmap.bmp",
        "https://example.com/scan.tiff",
    ]


def test_extract_image_urls_with_query_params() -> None:
    text = "Image with params: https://cdn.example.com/image.png?width=800&height=600"

    assert extract_image_urls(text) == ["https://cdn.example.com/image.png?width=800&height=600"]


def test_extract_image_urls_case_insensitive() -> None:
    text = "Mixed case: https://example.com/Image.PNG and https://example.com/photo.JpEg"

    assert extract_image_urls(text) == [
        "https://example.com/Image.PNG",
        "https://example.com/photo.JpEg",
    ]


def test_extract_image_urls_deduplication() -> None:
    text = "Same URL twice: https://example.com/image.png and again https://example.com/image.png"

    assert extract_image_urls(text) == ["https://example.com/image.png"]


def test_extract_image_urls_mixed_markdown_and_direct() -> None:
    text = (
        "Markdown: ![alt text](https://example.com/markdown.png) "
        "and direct: https://example.com/direct.jpg "
        "and another markdown ![](https://example.com/another.gif)"
    )

    result = extract_image_urls(text)
    assert set(result) == {
        "https://example.com/markdown.png",
        "https://example.com/direct.jpg",
        "https://example.com/another.gif",
    }
    assert len(result) == 3


# --- fetch_slack_text_files tests ---


def test_fetch_slack_text_files_fetches_from_url_private() -> None:
    messages = [
        {
            "files": [
                {
                    "title": "my snippet",
                    "preview": "hello...",
                    "url_private": "https://files.slack.com/files/snippet.txt",
                }
            ]
        }
    ]
    mock_response = AsyncMock()
    mock_response.text = "hello world"
    mock_response.raise_for_status = lambda: None

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    with patch.dict("os.environ", {"SLACK_BOT_TOKEN": "xoxb-test"}):
        result = asyncio.run(fetch_slack_text_files(messages, mock_client))

    assert len(result) == 1
    assert result[0] == {"title": "my snippet", "content": "hello world"}
    mock_client.get.assert_called_once()
    call_kwargs = mock_client.get.call_args
    assert call_kwargs[1]["headers"]["Authorization"] == "Bearer xoxb-test"


def test_fetch_slack_text_files_falls_back_to_inline_when_no_url() -> None:
    messages = [
        {
            "files": [
                {
                    "title": "inline snippet",
                    "plain_text": "inline content here",
                }
            ]
        }
    ]
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    result = asyncio.run(fetch_slack_text_files(messages, mock_client))

    assert len(result) == 1
    assert result[0] == {"title": "inline snippet", "content": "inline content here"}
    mock_client.get.assert_not_called()


def test_fetch_slack_text_files_falls_back_to_inline_on_fetch_error() -> None:
    messages = [
        {
            "files": [
                {
                    "title": "fallback snippet",
                    "url_private": "https://files.slack.com/files/fail.txt",
                    "preview": "preview content",
                }
            ]
        }
    ]
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.HTTPStatusError(
        "error", request=AsyncMock(), response=AsyncMock()
    )

    result = asyncio.run(fetch_slack_text_files(messages, mock_client))

    assert len(result) == 1
    assert result[0] == {"title": "fallback snippet", "content": "preview content"}


def test_fetch_slack_text_files_skips_binary_files() -> None:
    """Files without plain_text or preview are binary — should be skipped."""
    messages = [
        {
            "files": [
                {
                    "mimetype": "image/png",
                    "title": "screenshot.png",
                    "url_private": "https://files.slack.com/files/img.png",
                }
            ]
        }
    ]
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    result = asyncio.run(fetch_slack_text_files(messages, mock_client))

    assert result == []
    mock_client.get.assert_not_called()


def test_fetch_slack_text_files_truncates_large_content() -> None:
    messages = [
        {
            "files": [
                {
                    "title": "huge file",
                    "preview": "x" * 100,
                    "url_private": "https://files.slack.com/files/huge.txt",
                }
            ]
        }
    ]
    mock_response = AsyncMock()
    mock_response.text = "x" * 60_000
    mock_response.raise_for_status = lambda: None

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    result = asyncio.run(fetch_slack_text_files(messages, mock_client))

    assert len(result) == 1
    assert len(result[0]["content"]) == 50_000 + len("\n... (truncated)")
    assert result[0]["content"].endswith("\n... (truncated)")


def test_fetch_slack_text_files_no_files() -> None:
    messages = [{"text": "just a message"}]
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    result = asyncio.run(fetch_slack_text_files(messages, mock_client))

    assert result == []
