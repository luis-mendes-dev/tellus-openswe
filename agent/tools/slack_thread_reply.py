import asyncio
import os
from typing import Any

from langgraph.config import get_config
from langgraph_sdk import get_client

from ..utils.slack import (
    convert_mentions_to_slack_format,
    post_slack_thread_reply,
    store_slack_msg_run_mapping,
)

LANGGRAPH_URL = os.environ.get("LANGGRAPH_URL") or os.environ.get(
    "LANGGRAPH_URL_PROD", "http://localhost:2024"
)


def slack_thread_reply(message: str) -> dict[str, Any]:
    """Post a message to the current Slack thread.

    Format messages using Slack's mrkdwn format, NOT standard Markdown.
    Key differences: *bold*, _italic_, ~strikethrough~, <url|link text>,
    bullet lists with "• ", ```code blocks```, > blockquotes.
    Do NOT use **bold**, [link](url), or other standard Markdown syntax.

    To mention/tag a user, use Slack's mention format: <@USER_ID>.
    You can find user IDs in the conversation context (e.g. @Name(U06KD8BFY95)).
    Example: <@U06KD8BFY95> will tag that user in the message."""
    config = get_config()
    configurable = config.get("configurable", {})
    slack_thread = configurable.get("slack_thread", {})

    channel_id = slack_thread.get("channel_id")
    thread_ts = slack_thread.get("thread_ts")
    if not channel_id or not thread_ts:
        return {
            "success": False,
            "error": "Missing slack_thread.channel_id or slack_thread.thread_ts in config",
        }

    if not message.strip():
        return {"success": False, "error": "Message cannot be empty"}

    message = convert_mentions_to_slack_format(message)
    result_ts = asyncio.run(_post_and_store(channel_id, thread_ts, message))
    return {"success": result_ts is not None}


async def _post_and_store(channel_id: str, thread_ts: str, message: str) -> str | None:
    """Post a Slack reply and store the msg_ts → run_id mapping in one event loop."""
    result_ts = await post_slack_thread_reply(channel_id, thread_ts, message)
    if result_ts:
        client = get_client(url=LANGGRAPH_URL)
        await store_slack_msg_run_mapping(client, channel_id, thread_ts, result_ts)
    return result_ts
