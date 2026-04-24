"""Smoke: real squad-lead SOUL shows up in the rendered system prompt."""
from __future__ import annotations

from agent.tellus.prompt import construct_system_prompt


def test_real_soul_appears_in_rendered_prompt():
    rendered = construct_system_prompt(
        working_dir="/workspace",
        linear_project_id="TEL",
        linear_issue_number="1",
    )

    # SOUL identity
    assert "# Squad-Lead — Tellus Open-SWE" in rendered
    assert "You are the Tellus squad-lead." in rendered

    # SOUL pipeline stages
    for stage in ("Triage", "Plan", "Implement", "Self-QA", "Submit", "Notify"):
        assert stage in rendered, f"Stage '{stage}' missing from rendered prompt"

    # Runtime rules still present (prove we didn't clobber upstream)
    assert "Repository Setup" in rendered
    assert "commit_and_open_pr" in rendered

    # Separator between SOUL and upstream
    assert "\n---\n" in rendered
