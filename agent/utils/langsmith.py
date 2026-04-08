"""LangSmith trace URL and feedback utilities."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _compose_langsmith_url_base() -> str:
    """Build the LangSmith URL base from environment variables."""
    host_url = os.environ.get("LANGSMITH_URL_PROD", "https://smith.langchain.com")
    tenant_id = os.environ.get("LANGSMITH_TENANT_ID_PROD")
    project_id = os.environ.get("LANGSMITH_TRACING_PROJECT_ID_PROD")
    if not tenant_id or not project_id:
        raise ValueError(
            "LANGSMITH_TENANT_ID_PROD and LANGSMITH_TRACING_PROJECT_ID_PROD must be set"
        )
    return f"{host_url}/o/{tenant_id}/projects/p/{project_id}/r"


def get_langsmith_trace_url(run_id: str) -> str | None:
    """Build the LangSmith trace URL for a given run ID."""
    try:
        url_base = _compose_langsmith_url_base()
        return f"{url_base}/{run_id}?poll=true"
    except Exception:  # noqa: BLE001
        logger.warning("Failed to build LangSmith trace URL for run %s", run_id, exc_info=True)
        return None


def create_langsmith_feedback(
    run_id: str,
    key: str,
    score: float,
    *,
    comment: str | None = None,
    source_info: dict[str, Any] | None = None,
) -> bool:
    """Log feedback to LangSmith for a given run."""
    try:
        from langsmith import Client  # noqa: C0415

        client = Client()
        client.create_feedback(
            run_id=run_id,
            key=key,
            score=score,
            comment=comment,
            source_info=source_info,
        )
        logger.info("Logged LangSmith feedback for run %s: key=%s score=%s", run_id, key, score)
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Failed to log LangSmith feedback for run %s", run_id)
        return False
