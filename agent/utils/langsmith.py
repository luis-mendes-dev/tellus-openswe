"""LangSmith trace URL and feedback utilities."""

from __future__ import annotations

import logging
import os
from typing import Any

from langsmith import Client as LangSmithClient

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


def _build_langsmith_clients() -> list[LangSmithClient]:
    """Build LangSmith clients for all configured environments (prod + dev)."""
    clients: list[LangSmithClient] = []

    dev_api_key = os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")
    dev_api_url = os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
    if dev_api_key:
        clients.append(LangSmithClient(api_key=dev_api_key, api_url=dev_api_url))

    prod_api_key = os.environ.get("LANGSMITH_API_KEY_PROD")
    prod_api_url = os.environ.get("LANGSMITH_URL_PROD", "https://api.smith.langchain.com")
    if prod_api_key and prod_api_key != dev_api_key:
        clients.append(LangSmithClient(api_key=prod_api_key, api_url=prod_api_url))

    return clients


def create_langsmith_feedback(
    run_id: str,
    key: str,
    *,
    score: float | int | bool,
    comment: str | None = None,
    source_info: dict[str, Any] | None = None,
) -> bool:
    """Create feedback on a LangSmith run, dual-writing to all configured environments."""
    clients = _build_langsmith_clients()
    if not clients:
        logger.warning("No LangSmith clients configured for feedback")
        return False

    any_success = False
    for client in clients:
        try:
            client.create_feedback(
                run_id=run_id,
                key=key,
                score=score,
                comment=comment,
                source_info=source_info,
                feedback_source_type="api",
            )
            any_success = True
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to create LangSmith feedback for run %s on %s",
                run_id,
                client.api_url,
                exc_info=True,
            )
    return any_success
