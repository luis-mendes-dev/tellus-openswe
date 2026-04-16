import asyncio
from typing import Any

from ..utils.slack import (
    get_slack_user_names,
    parse_slack_message_url,
    resolve_slack_message_url,
)


async def _resolve_with_author(url: str) -> tuple[dict[str, Any] | None, str]:
    """Resolve a Slack message URL and look up the author name."""
    message = await resolve_slack_message_url(url)
    if not message:
        return None, ""
    user_id = message.get("user", "")
    author = user_id
    if user_id:
        names = await get_slack_user_names([user_id])
        author = names.get(user_id, user_id)
    return message, author


def read_slack_message(url: str) -> dict[str, Any]:
    """Read the content of a cross-posted Slack message link.

    Use this tool when you encounter a Slack message URL
    (e.g. https://workspace.slack.com/archives/C0AME1J0/p1776281321762829)
    and need to see the message content.

    Returns the message text, author, and any file attachments."""
    if not url or not url.strip():
        return {"success": False, "error": "URL cannot be empty"}

    cleaned = url.strip()
    if not parse_slack_message_url(cleaned):
        return {
            "success": False,
            "error": "Not a valid Slack message URL. Expected format: "
            "https://{workspace}.slack.com/archives/{channel_id}/p{timestamp}",
        }

    message, author = asyncio.run(_resolve_with_author(cleaned))
    if not message:
        return {
            "success": False,
            "error": "Could not fetch the Slack message. The bot may not have access to "
            "that channel, or the message may have been deleted.",
        }

    result: dict[str, Any] = {
        "success": True,
        "author": author,
        "text": message.get("text", ""),
        "channel_id": message.get("channel_id", ""),
        "ts": message.get("ts", ""),
    }

    files = message.get("files", [])
    if files:
        file_info = []
        for f in files:
            if isinstance(f, dict):
                file_info.append(
                    {
                        "name": f.get("name", ""),
                        "mimetype": f.get("mimetype", ""),
                        "url": f.get("url_private", ""),
                    }
                )
        if file_info:
            result["files"] = file_info

    if message.get("thread_ts"):
        result["thread_ts"] = message["thread_ts"]

    return result
