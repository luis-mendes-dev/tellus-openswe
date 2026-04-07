"""Linear Agent activity middleware.

Emits activities to Linear's Agents API during agent execution:
- After-tool keepalive: checks after every tool call if >= 25 minutes have
  passed since the last Linear activity. If so, emits an ephemeral thought
  to prevent the 30-minute stale timeout. Stores `last_linear_update_at`
  in thread metadata for persistence and visibility.
- After-agent completion: emits a response activity with the PR link
  when the agent finishes, marking the session as complete.

Only active when source == "linear-agent". Zero impact on other flows.
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentState, after_agent
from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.config import get_config
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.runtime import Runtime
from langgraph.types import Command
from langgraph_sdk import get_client

from ..utils.linear_agent import emit_error, emit_response, emit_thought

logger = logging.getLogger(__name__)

_KEEPALIVE_INTERVAL_SECONDS = 25 * 60  # 25 minutes


def _get_agent_session_id() -> str | None:
    """Extract agent_session_id from the current config, if present."""
    try:
        config = get_config()
        configurable = config.get("configurable", {})
        if configurable.get("source") != "linear-agent":
            return None
        return configurable.get("agent_session_id")
    except Exception:  # noqa: BLE001
        return None


class LinearAgentKeepalive(AgentMiddleware):
    """After-tool middleware that emits a keepalive thought to Linear.

    Checks after every tool call whether >= 25 minutes have passed since
    the last Linear activity update. If so, emits an ephemeral thought
    and stores the timestamp in thread metadata as `last_linear_update_at`.
    """

    state_schema = AgentState

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        result = handler(request)
        # Fire-and-forget the keepalive check (sync context, schedule async)
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(self._maybe_emit_keepalive())
            task.add_done_callback(
                lambda t: (
                    logger.exception("Keepalive task failed", exc_info=t.exception())
                    if t.exception()
                    else None
                )
            )
        except RuntimeError:
            logger.debug("No running event loop for keepalive (sync context)")
        except Exception:  # noqa: BLE001
            logger.exception("Failed to schedule keepalive task")
        return result

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        result = await handler(request)
        await self._maybe_emit_keepalive()
        return result

    async def _maybe_emit_keepalive(self) -> None:
        """Check if a keepalive is needed and emit if so."""
        session_id = _get_agent_session_id()
        if not session_id:
            return

        try:
            config = get_config()
            configurable = config.get("configurable", {})
            thread_id = configurable.get("thread_id")
            metadata = config.get("metadata", {})

            last_update = metadata.get("last_linear_update_at")
            now = time.time()

            if last_update is not None:
                elapsed = now - float(last_update)
                if elapsed < _KEEPALIVE_INTERVAL_SECONDS:
                    return
            else:
                # First tool call — set the initial timestamp, don't emit
                # (the background processor already emitted the initial thought)
                if thread_id:
                    langgraph_client = get_client()
                    await langgraph_client.threads.update(
                        thread_id=thread_id,
                        metadata={"last_linear_update_at": now},
                    )
                return

            # >= 25 min since last update — emit keepalive
            await emit_thought(session_id, "Still working on this...", ephemeral=True)
            logger.info("Emitted keepalive thought for agent session %s", session_id)

            # Update thread metadata with new timestamp
            if thread_id:
                langgraph_client = get_client()
                await langgraph_client.threads.update(
                    thread_id=thread_id,
                    metadata={"last_linear_update_at": now},
                )

        except Exception:
            logger.exception("Failed to emit keepalive for session %s", session_id)


# ---------------------------------------------------------------------------
# After-agent completion hook
# ---------------------------------------------------------------------------


def _extract_pr_url_from_messages(messages: list) -> str | None:
    """Extract PR URL from commit_and_open_pr tool result in messages."""
    for msg in reversed(messages):
        if isinstance(msg, dict):
            content = msg.get("content", "")
            name = msg.get("name", "")
        else:
            content = getattr(msg, "content", "")
            name = getattr(msg, "name", "")

        if name == "commit_and_open_pr" and content:
            try:
                parsed = _json.loads(content) if isinstance(content, str) else content
                if isinstance(parsed, dict) and parsed.get("success"):
                    return parsed.get("pr_url")
            except (ValueError, TypeError):
                pass
    return None


def _extract_last_ai_summary(messages: list) -> str:
    """Extract the last AI message text as a summary of work done."""
    for msg in reversed(messages):
        msg_type = msg.get("type", "") if isinstance(msg, dict) else getattr(msg, "type", "")
        if msg_type == "ai":
            content = (
                msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
            )
            # content can be a string or list of blocks
            if isinstance(content, str) and content.strip():
                return content.strip()
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        text_parts.append(block)
                text = "\n".join(text_parts).strip()
                if text:
                    return text
    return ""


@after_agent
async def linear_agent_completion(
    state: AgentState,
    runtime: Runtime,  # noqa: ARG001
) -> dict[str, Any] | None:
    """Emit a response or error activity when the agent finishes."""
    session_id = _get_agent_session_id()
    if not session_id:
        return None

    try:
        messages = state.get("messages", [])
        pr_url = _extract_pr_url_from_messages(messages)

        if pr_url:
            # Tag the triggering user so they get a notification
            config = get_config()
            triggering_user = (
                config.get("configurable", {})
                .get("linear_issue", {})
                .get("triggering_user_name", "")
            )
            tag_line = f"@{triggering_user} " if triggering_user else ""

            summary = _extract_last_ai_summary(messages)
            if summary:
                body = f"{tag_line}{summary}\n\nOpened a pull request: {pr_url}"
            else:
                body = f"{tag_line}Opened a pull request: {pr_url}"
            await emit_response(session_id, body)
            logger.info("Emitted completion response for session %s with PR %s", session_id, pr_url)

            # Move issue to "In Review"
            try:
                linear_issue = config.get("configurable", {}).get("linear_issue", {})
                issue_id = linear_issue.get("id") if isinstance(linear_issue, dict) else None
                if issue_id:
                    from ..utils.linear_agent import agent_update_issue_status

                    await agent_update_issue_status(issue_id, "In Review")
                    logger.info("Moved issue %s to 'In Review'", issue_id)
            except Exception:
                logger.exception("Failed to update issue status to 'In Review'")
        else:
            messaged_user = False
            for msg in reversed(messages):
                name = msg.get("name", "") if isinstance(msg, dict) else getattr(msg, "name", "")
                if name in ("linear_comment", "github_comment", "slack_thread_reply"):
                    messaged_user = True
                    break

            if messaged_user:
                await emit_response(session_id, "Done — posted a response on the issue.")
            else:
                await emit_response(session_id, "Finished working on this issue.")

            logger.info("Emitted completion response for session %s (no PR)", session_id)

    except Exception:
        logger.exception("Failed to emit completion activity for session %s", session_id)
        try:
            await emit_error(session_id, "An error occurred while completing the task.")
        except Exception:
            logger.exception("Failed to emit error activity for session %s", session_id)

    return None
