"""Slack reaction → LangSmith feedback processing."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from langgraph_sdk import get_client
from langgraph_sdk.client import LangGraphClient

from .langsmith import create_langsmith_feedback, delete_langsmith_feedback
from .slack import fetch_slack_thread_messages, lookup_run_id_for_slack_message

logger = logging.getLogger(__name__)

LANGGRAPH_URL = os.environ.get("LANGGRAPH_URL") or os.environ.get(
    "LANGGRAPH_URL_PROD", "http://localhost:2024"
)

FEEDBACK_REACTIONS: dict[str, float] = {
    "+1": 1.0,
    "thumbsup": 1.0,
    "-1": 0.0,
    "thumbsdown": 0.0,
}


async def _get_message_thread_ts(channel_id: str, message_ts: str) -> str | None:
    """Fetch the thread_ts for a Slack message (returns message_ts if it's a thread root)."""
    messages = await fetch_slack_thread_messages(channel_id, message_ts)
    if messages:
        first = messages[0]
        return first.get("thread_ts") or first.get("ts")
    return None


async def _compute_and_store_reaction_score(
    langgraph_client: LangGraphClient,
    run_id: str,
    user_id: str,
    channel_id: str,
    message_ts: str,
    reaction: str,
    *,
    add: bool,
) -> float | None:
    """Track active reactions per user/message in the store. Returns computed score or None if empty."""
    store_key = f"reactions:{user_id}:{message_ts}"
    namespace = ("slack_reaction_state", channel_id)
    try:
        item = await langgraph_client.store.get_item(namespace, store_key)
        reactions: list[str] = (item.get("value", {}) or {}).get("reactions", []) if item else []
    except Exception:  # noqa: BLE001
        reactions = []

    if add:
        if reaction not in reactions:
            reactions.append(reaction)
    else:
        if reaction in reactions:
            reactions.remove(reaction)

    try:
        await langgraph_client.store.put_item(namespace, store_key, {"reactions": reactions})
    except Exception:  # noqa: BLE001
        logger.debug("Failed to persist reaction state for %s", store_key)

    if not reactions:
        return None

    scores = [FEEDBACK_REACTIONS[r] for r in reactions if r in FEEDBACK_REACTIONS]
    if not scores:
        return None
    return sum(scores) / len(scores)


async def process_slack_reaction(event: dict[str, Any]) -> None:
    """Process a Slack reaction event and log LangSmith feedback."""
    reaction = event.get("reaction", "")
    score = FEEDBACK_REACTIONS.get(reaction)
    if score is None:
        return

    item = event.get("item", {})
    if item.get("type") != "message":
        return

    channel_id = item.get("channel", "")
    message_ts = item.get("ts", "")
    user_id = event.get("user", "")
    if not channel_id or not message_ts:
        return

    langgraph_client = get_client(url=LANGGRAPH_URL)

    thread_ts = await _get_message_thread_ts(channel_id, message_ts)

    run_id = await lookup_run_id_for_slack_message(
        langgraph_client, channel_id, message_ts, thread_ts
    )
    if not run_id:
        logger.debug(
            "No run_id found for Slack reaction on channel=%s message=%s",
            channel_id,
            message_ts,
        )
        return

    feedback_key = f"user_reaction:{user_id}"
    computed_score = await _compute_and_store_reaction_score(
        langgraph_client, run_id, user_id, channel_id, message_ts, reaction, add=True
    )
    if computed_score is None:
        return

    comment = f"Slack reactions from user {user_id}"
    success = await asyncio.to_thread(
        create_langsmith_feedback,
        run_id,
        feedback_key,
        score=computed_score,
        comment=comment,
        source_info={
            "source": "slack_reaction",
            "channel_id": channel_id,
            "message_ts": message_ts,
            "user_id": user_id,
        },
    )
    if success:
        logger.info(
            "Logged LangSmith feedback for run %s: reaction=%s computed_score=%s",
            run_id,
            reaction,
            computed_score,
        )
    else:
        logger.warning("Failed to log LangSmith feedback for run %s", run_id)


async def process_slack_reaction_removed(event: dict[str, Any]) -> None:
    """Process a Slack reaction_removed event and delete LangSmith feedback."""
    reaction = event.get("reaction", "")
    if reaction not in FEEDBACK_REACTIONS:
        return

    item = event.get("item", {})
    if item.get("type") != "message":
        return

    channel_id = item.get("channel", "")
    message_ts = item.get("ts", "")
    user_id = event.get("user", "")
    if not channel_id or not message_ts:
        return

    langgraph_client = get_client(url=LANGGRAPH_URL)
    thread_ts = await _get_message_thread_ts(channel_id, message_ts)

    run_id = await lookup_run_id_for_slack_message(
        langgraph_client, channel_id, message_ts, thread_ts
    )
    if not run_id:
        return

    feedback_key = f"user_reaction:{user_id}"
    computed_score = await _compute_and_store_reaction_score(
        langgraph_client, run_id, user_id, channel_id, message_ts, reaction, add=False
    )
    if computed_score is None:
        success = await asyncio.to_thread(delete_langsmith_feedback, run_id, feedback_key)
        if success:
            logger.info("Deleted LangSmith feedback for run %s: all reactions removed", run_id)
    else:
        success = await asyncio.to_thread(
            create_langsmith_feedback,
            run_id,
            feedback_key,
            score=computed_score,
            comment=f"Slack reactions from user {user_id}",
            source_info={
                "source": "slack_reaction",
                "channel_id": channel_id,
                "message_ts": message_ts,
                "user_id": user_id,
            },
        )
        if success:
            logger.info(
                "Updated LangSmith feedback for run %s: reaction=%s removed, score=%s",
                run_id,
                reaction,
                computed_score,
            )
