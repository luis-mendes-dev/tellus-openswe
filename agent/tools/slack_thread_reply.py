import asyncio
import os
from typing import Any

from langgraph.config import get_config
from langgraph_sdk import get_client

from ..utils.slack import convert_mentions_to_slack_format, post_slack_thread_reply

LANGGRAPH_URL = os.environ.get("LANGGRAPH_URL", "http://localhost:2024")


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
    result_ts = asyncio.run(post_slack_thread_reply(channel_id, thread_ts, message))
    if result_ts:
        asyncio.run(_store_msg_run_mapping(channel_id, thread_ts, result_ts))
    return {"success": result_ts is not None}


async def _store_msg_run_mapping(
    channel_id: str, thread_ts: str, msg_ts: str
) -> None:
    """Look up the run_id for the current thread and store a msg_ts mapping."""
    try:
        client = get_client(url=LANGGRAPH_URL)
        namespace = ("slack_run_map", channel_id)
        item = await client.store.get_item(namespace, f"thread:{thread_ts}")
        if item and item.get("value", {}).get("run_id"):
            run_id = item["value"]["run_id"]
            await client.store.put_item(namespace, f"msg:{msg_ts}", {"run_id": run_id})
    except Exception:  # noqa: BLE001
        pass
