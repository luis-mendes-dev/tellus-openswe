"""Before-model middleware that enforces a graceful step limit.

When the agent approaches the graph recursion limit, this middleware
injects a system-level instruction telling the agent to wrap up
immediately: commit any partial work, notify the user, and stop.

This prevents the agent from hitting the hard GraphRecursionError
(which crashes the run with no output or user notification) after
consuming significant tokens and cost.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain.agents.middleware import AgentState, before_model
from langchain_core.messages import HumanMessage
from langgraph.config import get_config
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)

# When the message count exceeds this fraction of the recursion limit,
# inject a "wrap up" instruction. Each agent turn typically adds 2-4
# messages (AI + tool calls + tool results), so we leave a generous
# buffer. The recursion limit counts graph *steps* (each message
# append is a step), so message count is a reasonable proxy.
STEP_LIMIT_FRACTION = 0.85


@before_model
async def step_limit_guard(
    state: AgentState,
    runtime: Runtime,  # noqa: ARG001
) -> dict[str, Any] | None:
    """Inject a wrap-up instruction when the agent is approaching the recursion limit.

    Counts the number of messages in state as a proxy for graph steps.
    When the count exceeds STEP_LIMIT_FRACTION of the configured
    recursion_limit, a human message is injected telling the agent to
    finish up immediately.
    """
    config = get_config()
    recursion_limit = config.get("recursion_limit", 1000)
    threshold = int(recursion_limit * STEP_LIMIT_FRACTION)

    message_count = len(state.get("messages", []))

    if message_count < threshold:
        return None

    logger.warning(
        "Step limit guard triggered: %d messages, threshold %d (limit %d). "
        "Injecting wrap-up instruction.",
        message_count,
        threshold,
        recursion_limit,
    )

    wrap_up_message = HumanMessage(
        content=(
            "[SYSTEM NOTICE — STEP LIMIT APPROACHING]\n\n"
            "You are approaching the maximum number of steps allowed for this run. "
            "You MUST wrap up immediately:\n\n"
            "1. If you have uncommitted changes, call `commit_and_open_pr` now with "
            "a title noting the work is partial.\n"
            "2. Notify the user via the appropriate channel (slack_thread_reply, "
            "linear_comment, or github_comment) that the task was too complex to "
            "complete in a single run and describe what was accomplished and what "
            "remains.\n"
            "3. Stop after notifying the user.\n\n"
            "Do NOT continue exploring or implementing. Wrap up NOW."
        ),
    )

    return {"messages": [wrap_up_message]}
