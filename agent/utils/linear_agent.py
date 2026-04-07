"""Linear Agents API utilities.

Handles OAuth token management, agent activity emission, session updates,
and promptContext XML parsing for the Linear Agents integration.

This module is separate from linear.py — it uses the agent's own OAuth token
(actor=app) instead of LINEAR_API_KEY, so openswe acts as its own identity.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import xml.etree.ElementTree as ET
from typing import Any

import httpx

logger = logging.getLogger(__name__)

LINEAR_API_URL = "https://api.linear.app/graphql"
LINEAR_OAUTH_TOKEN_URL = "https://api.linear.app/oauth/token"

# OAuth credentials — agent path only activates when ACCESS_TOKEN is set
LINEAR_AGENT_ACCESS_TOKEN = os.environ.get("LINEAR_AGENT_ACCESS_TOKEN", "")
LINEAR_AGENT_REFRESH_TOKEN = os.environ.get("LINEAR_AGENT_REFRESH_TOKEN", "")
LINEAR_AGENT_CLIENT_ID = os.environ.get("LINEAR_AGENT_CLIENT_ID", "")
LINEAR_AGENT_CLIENT_SECRET = os.environ.get("LINEAR_AGENT_CLIENT_SECRET", "")

# Token state (module-level, protected by lock)
_token_lock = threading.Lock()
_access_token = LINEAR_AGENT_ACCESS_TOKEN
_refresh_token = LINEAR_AGENT_REFRESH_TOKEN
_token_expires_at: float = 0.0  # unix timestamp; 0 means unknown/never refreshed


def is_agent_configured() -> bool:
    """Check if Linear Agent credentials are configured."""
    return bool(_access_token or LINEAR_AGENT_ACCESS_TOKEN)


def _get_access_token() -> str:
    """Get the current access token (thread-safe)."""
    with _token_lock:
        return _access_token


async def _refresh_access_token() -> bool:
    """Refresh the OAuth access token using the refresh token.

    Returns True if refresh succeeded, False otherwise.
    """
    global _access_token, _refresh_token, _token_expires_at  # noqa: PLW0603

    refresh_tok = _refresh_token
    if not refresh_tok or not LINEAR_AGENT_CLIENT_ID or not LINEAR_AGENT_CLIENT_SECRET:
        logger.warning("Cannot refresh token: missing refresh token or client credentials")
        return False

    async with httpx.AsyncClient() as http_client:
        try:
            response = await http_client.post(
                LINEAR_OAUTH_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_tok,
                    "client_id": LINEAR_AGENT_CLIENT_ID,
                    "client_secret": LINEAR_AGENT_CLIENT_SECRET,
                },
            )
            response.raise_for_status()
            data = response.json()

            with _token_lock:
                _access_token = data["access_token"]
                if "refresh_token" in data:
                    _refresh_token = data["refresh_token"]
                # Linear tokens are valid for 24 hours; refresh at 23h
                _token_expires_at = time.time() + (23 * 3600)

            logger.info("Linear agent OAuth token refreshed successfully")
            return True
        except Exception:
            logger.exception("Failed to refresh Linear agent OAuth token")
            return False


async def _ensure_valid_token() -> str | None:
    """Ensure we have a valid access token, refreshing if needed.

    Returns the access token, or None if unavailable.
    """
    token = _get_access_token()
    if not token:
        return None

    # If we know the token is expired, try to refresh
    if _token_expires_at > 0 and time.time() >= _token_expires_at:
        refreshed = await _refresh_access_token()
        if not refreshed:
            # Use the old token as a last resort — it might still work
            logger.warning("Token refresh failed, using existing token")
        return _get_access_token()

    return token


def _agent_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


async def _agent_graphql_request(
    query: str, variables: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Execute a GraphQL request using the agent's OAuth token."""
    token = await _ensure_valid_token()
    if not token:
        return {"error": "LINEAR_AGENT_ACCESS_TOKEN is not configured"}

    async with httpx.AsyncClient() as http_client:
        try:
            response = await http_client.post(
                LINEAR_API_URL,
                headers=_agent_headers(token),
                json={"query": query, "variables": variables or {}},
            )

            # If we get a 401, try refreshing the token once
            if response.status_code == 401:
                logger.info("Got 401 from Linear API, attempting token refresh")
                refreshed = await _refresh_access_token()
                if refreshed:
                    new_token = _get_access_token()
                    response = await http_client.post(
                        LINEAR_API_URL,
                        headers=_agent_headers(new_token),
                        json={"query": query, "variables": variables or {}},
                    )

            response.raise_for_status()
            result = response.json()
            if result.get("errors"):
                logger.error("Linear agent GraphQL errors: %s", result["errors"])
                return {"error": result["errors"]}
            return result.get("data", {})
        except Exception as e:  # noqa: BLE001
            logger.exception("Linear agent GraphQL request failed")
            return {"error": str(e)}


# ---------------------------------------------------------------------------
# Agent Activity Emission
# ---------------------------------------------------------------------------

_ACTIVITY_CREATE_MUTATION = """
mutation AgentActivityCreate($input: AgentActivityCreateInput!) {
    agentActivityCreate(input: $input) {
        success
        agentActivity {
            id
        }
    }
}
"""


async def emit_thought(session_id: str, body: str, *, ephemeral: bool = False) -> bool:
    """Emit a thought activity on an agent session."""
    result = await _agent_graphql_request(
        _ACTIVITY_CREATE_MUTATION,
        {
            "input": {
                "agentSessionId": session_id,
                "content": {"type": "thought", "body": body},
                "ephemeral": ephemeral,
            }
        },
    )
    success = bool(result.get("agentActivityCreate", {}).get("success"))
    if not success:
        logger.error("Failed to emit thought for session %s: %s", session_id, result)
    return success


async def emit_response(session_id: str, body: str) -> bool:
    """Emit a response activity — marks the session as complete."""
    result = await _agent_graphql_request(
        _ACTIVITY_CREATE_MUTATION,
        {
            "input": {
                "agentSessionId": session_id,
                "content": {"type": "response", "body": body},
            }
        },
    )
    success = bool(result.get("agentActivityCreate", {}).get("success"))
    if not success:
        logger.error("Failed to emit response for session %s: %s", session_id, result)
    return success


async def emit_error(session_id: str, body: str) -> bool:
    """Emit an error activity — marks the session as errored."""
    result = await _agent_graphql_request(
        _ACTIVITY_CREATE_MUTATION,
        {
            "input": {
                "agentSessionId": session_id,
                "content": {"type": "error", "body": body},
            }
        },
    )
    success = bool(result.get("agentActivityCreate", {}).get("success"))
    if not success:
        logger.error("Failed to emit error for session %s: %s", session_id, result)
    return success


# ---------------------------------------------------------------------------
# Session Management
# ---------------------------------------------------------------------------

_SESSION_UPDATE_MUTATION = """
mutation AgentSessionUpdate($id: String!, $input: AgentSessionUpdateInput!) {
    agentSessionUpdate(id: $id, input: $input) {
        success
    }
}
"""


async def update_session_external_urls(
    session_id: str,
    urls: list[dict[str, str]],
) -> bool:
    """Add external URLs to an agent session (e.g., trace link, PR link)."""
    result = await _agent_graphql_request(
        _SESSION_UPDATE_MUTATION,
        {
            "id": session_id,
            "input": {
                "addedExternalUrls": urls,
            },
        },
    )
    return bool(result.get("agentSessionUpdate", {}).get("success"))


# ---------------------------------------------------------------------------
# Issue Status Update (via agent identity)
# ---------------------------------------------------------------------------


async def agent_update_issue_status(issue_id: str, status_name: str) -> dict[str, Any]:
    """Update a Linear issue's workflow status using the agent's OAuth token.

    Same logic as linear.update_issue_status but uses the agent identity
    so the status change appears as "Openswe-dev moved..." instead of the user.
    """
    # Get the issue to find its team
    issue_query = """
    query GetIssue($id: String!) {
        issue(id: $id) {
            id
            team { id }
        }
    }
    """
    issue_result = await _agent_graphql_request(issue_query, {"id": issue_id})
    if "error" in issue_result:
        return issue_result

    issue = issue_result.get("issue")
    if not issue:
        return {"error": f"Issue {issue_id} not found"}

    team = issue.get("team", {})
    team_id = team.get("id") if team else None
    if not team_id:
        return {"error": "Could not determine team for issue"}

    # Get team workflow states
    states_query = """
    query GetTeamStates($teamId: String!) {
        team(id: $teamId) {
            states {
                nodes { id name type }
            }
        }
    }
    """
    states_result = await _agent_graphql_request(states_query, {"teamId": team_id})
    if "error" in states_result:
        return states_result

    states = states_result.get("team", {}).get("states", {}).get("nodes", [])
    if not states:
        return {"error": f"No workflow states found for team {team_id}"}

    # Find matching state
    target_state = None
    for state in states:
        if state.get("name", "").lower() == status_name.lower():
            target_state = state
            break

    if not target_state:
        available = [s.get("name") for s in states]
        logger.warning("Status '%s' not found. Available: %s", status_name, available)
        return {"error": f"Status '{status_name}' not found. Available: {available}"}

    # Update the issue state via agent token
    mutation = """
    mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
        issueUpdate(id: $id, input: $input) {
            success
            issue { id identifier }
        }
    }
    """
    result = await _agent_graphql_request(
        mutation, {"id": issue_id, "input": {"stateId": target_state["id"]}}
    )
    if "error" in result:
        return result
    return {"success": result.get("issueUpdate", {}).get("success", False)}


# ---------------------------------------------------------------------------
# promptContext XML Parser
# ---------------------------------------------------------------------------


def parse_prompt_context(xml_string: str) -> dict[str, Any]:
    """Parse the promptContext XML from an AgentSessionEvent.

    Returns a dict with:
        - identifier: str (e.g., "ENG-123")
        - title: str
        - description: str
        - team_name: str
        - labels: list[str]
        - project_name: str
        - parent_issue: dict | None
        - comments: list[dict] (author, created_at, body)
        - guidance: list[dict] (origin, team_name, body)
    """
    result: dict[str, Any] = {
        "identifier": "",
        "title": "",
        "description": "",
        "team_name": "",
        "labels": [],
        "project_name": "",
        "parent_issue": None,
        "comments": [],
        "guidance": [],
    }

    if not xml_string or not xml_string.strip():
        return result

    # Wrap in a root element since promptContext may have multiple top-level elements
    wrapped = f"<root>{xml_string}</root>"
    try:
        root = ET.fromstring(wrapped)  # noqa: S314
    except ET.ParseError:
        logger.exception("Failed to parse promptContext XML")
        return result

    # Parse <issue>
    issue_el = root.find("issue")
    if issue_el is not None:
        result["identifier"] = issue_el.get("identifier", "")

        title_el = issue_el.find("title")
        if title_el is not None and title_el.text:
            result["title"] = title_el.text.strip()

        desc_el = issue_el.find("description")
        if desc_el is not None and desc_el.text:
            result["description"] = desc_el.text.strip()

        team_el = issue_el.find("team")
        if team_el is not None:
            result["team_name"] = team_el.get("name", "")

        for label_el in issue_el.findall("label"):
            if label_el.text:
                result["labels"].append(label_el.text.strip())

        project_el = issue_el.find("project")
        if project_el is not None:
            result["project_name"] = project_el.get("name", "")

        parent_el = issue_el.find("parent-issue")
        if parent_el is not None:
            result["parent_issue"] = {
                "identifier": parent_el.get("identifier", ""),
                "title": parent_el.text.strip() if parent_el.text else "",
            }

    # Parse <primary-directive-thread>
    thread_el = root.find("primary-directive-thread")
    if thread_el is not None:
        for comment_el in thread_el.findall("comment"):
            result["comments"].append(
                {
                    "author": comment_el.get("author", ""),
                    "created_at": comment_el.get("created-at", ""),
                    "body": comment_el.text.strip() if comment_el.text else "",
                }
            )

    # Parse <guidance>
    guidance_el = root.find("guidance")
    if guidance_el is not None:
        for rule_el in guidance_el.findall("guidance-rule"):
            result["guidance"].append(
                {
                    "origin": rule_el.get("origin", ""),
                    "team_name": rule_el.get("team-name", ""),
                    "body": rule_el.text.strip() if rule_el.text else "",
                }
            )

    return result
