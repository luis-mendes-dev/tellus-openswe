import asyncio
from typing import Any

import httpx
from langgraph.config import get_config

from ..utils.github_app import get_github_app_installation_token

GITHUB_API_BASE = "https://api.github.com"

MAX_LOG_LINES = 500


def _get_repo_config() -> dict[str, str]:
    config = get_config()
    return config.get("configurable", {}).get("repo", {})


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def _get_token() -> str | None:
    return await get_github_app_installation_token()


def _repo_url(repo_config: dict[str, str]) -> str:
    owner = repo_config.get("owner", "")
    name = repo_config.get("name", "")
    return f"{GITHUB_API_BASE}/repos/{owner}/{name}"


def get_ci_status(pull_number: int) -> dict[str, Any]:
    """Get CI status for a pull request, filtered to only required check groups.

    Fetches branch protection rules to determine which checks are required,
    then returns failing jobs only from workflow run groups that contain
    at least one required check. This filters out non-blocking CI failures.

    Args:
        pull_number: The PR number to check CI status for.

    Returns:
        Dictionary with overall status, required check contexts, and failing
        jobs with job_id (use with get_ci_logs to fetch failure logs).
    """
    repo_config = _get_repo_config()
    if not repo_config:
        return {"success": False, "error": "No repo config found"}

    token = asyncio.run(_get_token())
    if not token:
        return {"success": False, "error": "Failed to get GitHub App installation token"}

    base_url = _repo_url(repo_config)

    async def _fetch() -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            # 1. Get PR head SHA and base branch
            pr_resp = await client.get(
                f"{base_url}/pulls/{pull_number}",
                headers=_github_headers(token),
            )
            if pr_resp.status_code != 200:
                return {
                    "success": False,
                    "error": f"Failed to fetch PR: {pr_resp.status_code}: {pr_resp.text}",
                }
            pr_data = pr_resp.json()
            head_sha = pr_data["head"]["sha"]
            base_branch = pr_data["base"]["ref"]

            # 2. Get required check contexts from branch protection
            protection_resp = await client.get(
                f"{base_url}/branches/{base_branch}/protection/required_status_checks",
                headers=_github_headers(token),
            )
            required_contexts: set[str] = set()
            has_required_checks = False
            if protection_resp.status_code == 200:
                has_required_checks = True
                protection_data = protection_resp.json()
                for check in protection_data.get("checks", []):
                    required_contexts.add(check.get("context", ""))
                for ctx in protection_data.get("contexts", []):
                    required_contexts.add(ctx)
                required_contexts.discard("")

            # 3. Get workflow runs for the head SHA
            runs_resp = await client.get(
                f"{base_url}/actions/runs",
                headers=_github_headers(token),
                params={"head_sha": head_sha},
            )
            if runs_resp.status_code != 200:
                return {
                    "success": False,
                    "error": f"Failed to fetch workflow runs: {runs_resp.status_code}: {runs_resp.text}",
                }

            workflow_runs = runs_resp.json().get("workflow_runs", [])
            if not workflow_runs:
                return {
                    "success": True,
                    "status": "no_runs",
                    "message": "No CI workflow runs found for this PR's latest commit.",
                    "head_sha": head_sha,
                    "required_contexts": sorted(required_contexts),
                    "failing_jobs": [],
                }

            # 4. Get jobs for each workflow run and filter
            failing_jobs = []
            for run in workflow_runs:
                jobs_resp = await client.get(
                    f"{base_url}/actions/runs/{run['id']}/jobs",
                    headers=_github_headers(token),
                )
                if jobs_resp.status_code != 200:
                    continue

                jobs = jobs_resp.json().get("jobs", [])

                # If we have required checks info, filter to only groups
                # containing a required check. Otherwise, include all groups.
                if has_required_checks:
                    group_has_required = any(
                        job["name"] in required_contexts for job in jobs
                    )
                    if not group_has_required:
                        continue

                # Include all failing jobs from this group
                for job in jobs:
                    if job.get("conclusion") == "failure":
                        failing_jobs.append(
                            {
                                "job_id": job["id"],
                                "name": job["name"],
                                "status": job["status"],
                                "conclusion": job.get("conclusion"),
                                "workflow": run.get("name", ""),
                                "html_url": job.get("html_url", ""),
                            }
                        )

            if failing_jobs:
                overall = "failure"
            else:
                # Check if any jobs are still pending
                has_pending = False
                for run in workflow_runs:
                    jobs_resp = await client.get(
                        f"{base_url}/actions/runs/{run['id']}/jobs",
                        headers=_github_headers(token),
                    )
                    if jobs_resp.status_code != 200:
                        continue
                    for job in jobs_resp.json().get("jobs", []):
                        is_relevant = (
                            not has_required_checks
                            or job["name"] in required_contexts
                        )
                        if (
                            is_relevant
                            and job["status"] in ("queued", "in_progress")
                        ):
                            has_pending = True
                            break
                    if has_pending:
                        break
                overall = "pending" if has_pending else "success"

            result: dict[str, Any] = {
                "success": True,
                "status": overall,
                "head_sha": head_sha,
                "failing_jobs": failing_jobs,
            }
            if has_required_checks:
                result["required_contexts"] = sorted(required_contexts)
            else:
                result["note"] = (
                    "Could not determine required checks (branch protection not accessible). "
                    "All failing jobs are reported. Treat all failures as potentially blocking."
                )
            return result

    return asyncio.run(_fetch())


def get_ci_logs(job_id: int) -> dict[str, Any]:
    """Get logs for a specific CI job.

    Args:
        job_id: The GitHub Actions job ID (from get_ci_status results).

    Returns:
        Dictionary with success status and the job's log output.
        Logs are truncated to the last 500 lines if too long.
    """
    repo_config = _get_repo_config()
    if not repo_config:
        return {"success": False, "error": "No repo config found"}

    token = asyncio.run(_get_token())
    if not token:
        return {"success": False, "error": "Failed to get GitHub App installation token"}

    url = f"{_repo_url(repo_config)}/actions/jobs/{job_id}/logs"

    async def _fetch() -> dict[str, Any]:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers=_github_headers(token))
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"GitHub API returned {response.status_code}: {response.text}",
                }

            log_text = response.text
            lines = log_text.splitlines()
            total_lines = len(lines)
            truncated = total_lines > MAX_LOG_LINES
            if truncated:
                lines = lines[-MAX_LOG_LINES:]

            return {
                "success": True,
                "job_id": job_id,
                "log": "\n".join(lines),
                "truncated": truncated,
                "total_lines": total_lines,
            }

    return asyncio.run(_fetch())
