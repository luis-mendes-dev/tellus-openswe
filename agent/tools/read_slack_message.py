import asyncio
from typing import Any

from ..utils.slack import (
    extract_slack_message_urls,
    get_slack_user_names,
    resolve_slack_message_url,
)


def read_slack_message(url: str) -> dict[str, Any]:
    """Read the content of a cross-posted Slack message link.

    Use this tool when you encounter a Slack message URL
    (e.g. https://workspace.slack.com/archives/C0AME1J0/p1776281321762829)
    and need to see the message content.

    Returns the message text, author, and any file attachments."""
    if not url or not url.strip():
        return {"success": False, "error": "URL cannot be empty"}

    links = extract_slack_message_urls(url.strip())
    if not links:
        return {
            "success": False,
            "error": "Not a valid Slack message URL. Expected format: "
            "https://{workspace}.slack.com/archives/{channel_id}/p{timestamp}",
        }

    message = asyncio.run(resolve_slack_message_url(url.strip()))
    if not message:
        return {
            "success": False,
            "error": "Could not fetch the Slack message. The bot may not have access to "
            "that channel, or the message may have been deleted.",
        }

    user_id = message.get("user", "")
    user_name = user_id
    if user_id:
        names = asyncio.run(get_slack_user_names([user_id]))
        user_name = names.get(user_id, user_id)

    result: dict[str, Any] = {
        "success": True,
        "author": user_name,
        "text": message.get("text", ""),
        "channel_id": message.get("channel_id", ""),
        "ts": message.get("ts", ""),
    }

    files = message.get("files", [])
    if files:
        file_info = []
        for f in files:
            if isinstance(f, dict):
                file_info.append({
                    "name": f.get("name", ""),
                    "mimetype": f.get("mimetype", ""),
                    "url": f.get("url_private", ""),
                })
        if file_info:
            result["files"] = file_info

    if message.get("thread_ts"):
        result["thread_ts"] = message["thread_ts"]

    return result
