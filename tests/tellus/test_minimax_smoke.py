"""Live smoke test against MiniMax's OpenAI-compatible endpoint.

Skipped automatically unless MINIMAX_API_KEY is set. Exists to catch
provider-side drift (endpoint URL changes, tool-calling regressions) that
unit tests cannot.
"""
from __future__ import annotations

import os

import pytest
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from agent.tellus.models import make_model

LIVE = os.environ.get("MINIMAX_API_KEY") is not None

pytestmark = pytest.mark.skipif(not LIVE, reason="MINIMAX_API_KEY not set")


@tool
def add(a: int, b: int) -> int:
    """Return a + b."""
    return a + b


def test_minimax_tool_call_round_trip():
    model = make_model("minimax:MiniMax-M1", max_tokens=200).bind_tools([add])

    response = model.invoke([HumanMessage(content="Use the add tool to compute 21 + 21.")])

    tool_calls = getattr(response, "tool_calls", None) or []
    assert tool_calls, f"Expected at least one tool call, got response={response!r}"
    assert tool_calls[0]["name"] == "add"
    args = tool_calls[0]["args"]
    assert int(args.get("a", 0)) == 21
    assert int(args.get("b", 0)) == 21
