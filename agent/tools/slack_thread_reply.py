import asyncio
from typing import Any

from langgraph.config import get_config

from ..utils.slack import convert_mentions_to_slack_format, post_slack_thread_reply


def _store_message_run_mapping(channel_id: str, message_ts: str, run_id: str) -> None:
    """Store a Slack message_ts → run_id mapping (best-effort)."""
    from ..webapp import store_slack_message_run_mapping

    try:
        asyncio.run(store_slack_message_run_mapping(channel_id, message_ts, run_id))
    except Exception:  # noqa: BLE001
        pass


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
    message_ts = asyncio.run(post_slack_thread_reply(channel_id, thread_ts, message))

    if message_ts:
        run_id = config.get("run_id") or configurable.get("run_id")
        if run_id:
            _store_message_run_mapping(channel_id, message_ts, str(run_id))

    return {"success": bool(message_ts)}
