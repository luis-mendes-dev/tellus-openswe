# Skill: Plan Writing

Write plans that tell the implementer WHAT and WHY - never HOW. Method
signatures, query strategies, test body contents belong to the implementer.

## Plan file format

Save to `/workspace/plan.md` in the sandbox. One plan file per ticket.

```markdown
# <ISSUE_ID>: <TITLE> - Implementation Plan

**Goal:** One sentence - desired end state once all tasks complete.
**Architecture:** 2-3 sentences on approach. Name the file groups touched.
**Tech Stack:** The actual languages / frameworks the repo uses.

---

### Task N: <what this accomplishes>

**Goal:** One sentence - desired behavior change.
**Scope:** Exact file paths that will be touched and their test files.
**Constraints:** Backward-compatibility, existing-pattern requirements,
performance / security requirements. No method names, no SQL, no test
body descriptions.
**Depends on:** Task M, or "none".
**Success criteria:** Observable, verifiable outcomes - a shell command
that exits 0, a test name that passes, an HTTP response shape. Bad:
"endpoint works". Good: "GET /api/x returns 200 with field y".
**Commit:** `<type>(<ISSUE_ID>): <what this task accomplishes>`
**Estimated minutes:** N. If >30, decompose into sub-tasks that each
fit within 30.
```

## Self-validation before returning the plan

Before returning control to the squad-lead, confirm each of the following:

1. Every file path referenced in `Scope` is reachable from `/workspace/<repo>/`.
2. Every success criterion starts with an executable verification - a test
   command, a curl invocation, or an HTTP response assertion.
3. Every task has `estimated_minutes <= 30`.
4. The plan contains no method signatures, no SQL fragments, no prescribed
   test body text.

If any check fails, revise the plan before returning.

## Scope discipline

Scope is only what the ticket requires (YAGNI). If you discover adjacent
issues, note them at the end of the plan in a `## Follow-ups` section and
do not include them as tasks.
