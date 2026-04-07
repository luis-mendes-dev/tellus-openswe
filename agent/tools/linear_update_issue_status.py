import asyncio
from typing import Any

from ..utils.linear import update_issue_status


def linear_update_issue_status(
    issue_id: str,
    status_name: str,
) -> dict[str, Any]:
    """Update a Linear issue's workflow status by name.

    Args:
        issue_id: The Linear issue UUID to update.
        status_name: The target status name, e.g. "In Progress", "In Review", "Done".

    Returns:
        Dictionary with 'success' bool and updated 'issue' details,
        or 'error' if the status name was not found.
    """
    return asyncio.run(update_issue_status(issue_id=issue_id, status_name=status_name))
