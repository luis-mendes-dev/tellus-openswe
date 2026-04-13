"""Tests for github_review tool guards."""

from unittest.mock import patch

import pytest

from agent.tools.github_review import create_pr_review, submit_pr_review


class TestApproveBlocked:
    """APPROVE event must be rejected in both create and submit."""

    @pytest.mark.asyncio
    async def test_create_pr_review_blocks_approve(self):
        result = await create_pr_review(pull_number=1, body="lgtm", event="APPROVE")
        assert result["success"] is False
        assert "APPROVE is not allowed" in result["error"]

    @pytest.mark.asyncio
    async def test_submit_pr_review_blocks_approve(self):
        result = await submit_pr_review(pull_number=1, review_id=1, event="APPROVE")
        assert result["success"] is False
        assert "APPROVE is not allowed" in result["error"]

    @pytest.mark.asyncio
    async def test_create_pr_review_blocks_approve_lowercase(self):
        result = await create_pr_review(pull_number=1, body="lgtm", event="approve")
        assert result["success"] is False
        assert "APPROVE is not allowed" in result["error"]

    @pytest.mark.asyncio
    async def test_submit_pr_review_blocks_approve_mixed_case(self):
        result = await submit_pr_review(pull_number=1, review_id=1, event="Approve")
        assert result["success"] is False
        assert "APPROVE is not allowed" in result["error"]

    @pytest.mark.asyncio
    @patch("agent.tools.github_review._get_repo_config", return_value=None)
    async def test_create_pr_review_allows_comment(self, _mock):
        result = await create_pr_review(pull_number=1, body="looks good", event="COMMENT")
        # Will fail with "No repo config found" but NOT with the approve error
        assert "APPROVE is not allowed" not in result.get("error", "")

    @pytest.mark.asyncio
    @patch("agent.tools.github_review._get_repo_config", return_value=None)
    async def test_create_pr_review_allows_request_changes(self, _mock):
        result = await create_pr_review(pull_number=1, body="fix this", event="REQUEST_CHANGES")
        assert "APPROVE is not allowed" not in result.get("error", "")
