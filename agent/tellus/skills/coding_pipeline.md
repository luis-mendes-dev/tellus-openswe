# Skill: Coding Pipeline

Every ticket passes through the same stages. Name the stage you are in
before you act in it. Never skip.

1. **Triage** - Classify: bug, feature, refactor, infra, docs. Identify
   the target repo and the affected module. If the ticket is ambiguous,
   ask a focused question in the source channel and stop.
2. **Plan** - Produce a written plan (see the Plan Writing skill).
3. **Sanity-check the plan** - Re-read. Is it addressing the real root
   cause? Would a senior colleague accept it? Shrink if it overreaches.
4. **Implement** - Make the minimal change. Do not refactor adjacent code
   that the ticket does not require. Keep the diff focused.
5. **Self-QA** - Compliance (scope + AGENTS.md), security (secrets, auth,
   PII, injection), testing (run tests that exercise the changed code).
6. **Submit** - Call `commit_and_open_pr` with a draft PR. Title under 70
   chars, body under 10 lines, include a Test Plan section with
   novel verification steps only.
7. **Notify** - Post a Linear / Slack / GitHub comment that @-mentions the
   requester and links the PR.

## Pipeline rules

- Plan before code. No `write_file` against source before a plan exists.
- Do not widen scope mid-ticket. Follow-ups go in the PR body, not in
  the commit.
- Never commit secrets. If one would be needed, stop and ask for a vault
  reference.
- Respect `AGENTS.md`. If it conflicts with anything else, AGENTS.md wins.
