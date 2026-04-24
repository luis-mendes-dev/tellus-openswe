"""Tellus model factory.

Adds a `minimax:<model>` prefix that resolves to LangChain's OpenAI provider
pointed at MiniMax's OpenAI-compatible endpoint. All other prefixes
(`anthropic:`, `openai:`, `google_genai:`, ...) fall through to upstream
`agent.utils.model.make_model` unchanged.

Env vars read:
    MINIMAX_API_KEY   - required for `minimax:` prefix
    MINIMAX_BASE_URL  - optional override; default https://api.minimax.io/v1
    LLM_MODEL_ID      - default model id when none is passed
"""
from __future__ import annotations

import os

from langchain.chat_models import init_chat_model

from agent.utils.model import make_model as _upstream_make_model

MINIMAX_DEFAULT_BASE_URL = "https://api.minimax.io/v1"
DEFAULT_LLM_MODEL_ID = "minimax:MiniMax-M1"


def make_model(model_id: str | None = None, **kwargs):
    """Create a chat model. Supports a `minimax:` prefix on top of upstream."""
    effective_id = model_id or os.environ.get("LLM_MODEL_ID", DEFAULT_LLM_MODEL_ID)

    if effective_id.startswith("minimax:"):
        model_name = effective_id.split(":", 1)[1]
        model_kwargs = dict(kwargs)
        model_kwargs["base_url"] = os.environ.get(
            "MINIMAX_BASE_URL", MINIMAX_DEFAULT_BASE_URL
        )
        model_kwargs["api_key"] = os.environ["MINIMAX_API_KEY"]
        return init_chat_model(model=f"openai:{model_name}", **model_kwargs)

    return _upstream_make_model(effective_id, **kwargs)
