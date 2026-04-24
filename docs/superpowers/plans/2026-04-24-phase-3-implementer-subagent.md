# Phase 3 — Implementer Subagent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the implementer subagent. The squad-lead stops writing source itself: it delegates planning to the planner, then delegates code changes to the implementer, then opens the PR. The implementer reads `/workspace/plan.md`, edits code in the sandbox, runs the tests that exercise its changes, and returns a terse summary.

**Architecture:** Extend `SUBAGENTS` with a second entry (`implementer`). Port the Aegis implementer SOUL into `agent/tellus/souls/implementer.md`. Add two more skills (`tdd.md`, `verification.md`) to `agent/tellus/skills/` and extend `ROLE_SKILLS` to map them. For the first time, set explicit `tools=[]` on both subagents: deepagents auto-wires the sandbox filesystem + shell middleware for every subagent, so an empty `tools` list denies the main agent's repo/Linear/PR-opening tools without denying file edits or test runs. Revise `agent/tellus/souls/squad_lead.md` to replace "implementer aspirational" wording with concrete delegation + commit ownership rules.

**Tech Stack:** Python 3.12, `deepagents.middleware.subagents.SubAgent`, LangSmith Sandbox. No new third-party deps.

**Pre-requisites:**
- Phase 2 complete: `SUBAGENTS` exists with planner, `skill_loader.py` + `plan_writing` + `coding_pipeline` skills live, squad-lead SOUL has Phase 2 planner delegation rules.
- `origin/main` at `3434ab75` or later.

**Non-goals:**
- QA / fixer / PR-creator subagents — Phases 4, 5.
- Middleware-based tool enforcement (path-level write restrictions, commit guards). Agentic enforcement via SOUL only in Phase 3.
- Institutional memory or learning pipelines.

---

## File Structure

**New files (all under `agent/tellus/`):**

| File | Responsibility |
|---|---|
| `agent/tellus/skills/tdd.md` | Ported from Aegis `skills/custom/tdd/`. Red-green-refactor, test-first rule, no commit without green. |
| `agent/tellus/skills/verification.md` | Runs the right tests for the right scope — changed-file specs, lint, no full suite. |
| `agent/tellus/souls/implementer.md` | Tellus implementer SOUL — reads plan, edits repo, runs tests, commits locally, returns summary. |

**Modified files:**

| File | Change |
|---|---|
| `agent/tellus/skill_loader.py` | Extend `ROLE_SKILLS` to map `implementer → [coding_pipeline, tdd, verification]`. |
| `agent/tellus/subagents.py` | Add implementer entry; set explicit `tools=[]` on both subagents; keep shared `_build_system_prompt` helper. |
| `agent/tellus/souls/squad_lead.md` | Replace "Implementer (aspirational — Phase 3)" line + remove the "today, you execute the plan yourself" clause for the implement stage. Add a `## Delegation rule for the implementer` block. Keep QA / fixer / PR-creator sections aspirational. |
| `agent/tellus/README.md` | Append Phase 3 diff-log entry (no new upstream diff — `server.py` untouched). |
| `tests/tellus/test_subagents.py` | Extend tests to cover the implementer entry (shape, SOUL + skills, tool restriction). Keep existing planner tests. |
| `tests/tellus/test_skill_loader.py` | Extend `ROLE_SKILLS` fixture test to assert `implementer` role maps to the right skills. |

**Untouched:** `agent/server.py` (no new imports, no new kwargs — `SUBAGENTS` already wired in Phase 2), all upstream files.

---

## Task 1: Port the TDD and verification skills

**Files:**
- Create: `agent/tellus/skills/tdd.md`
- Create: `agent/tellus/skills/verification.md`

**Context:** Two skills, short, runtime-relevant. Drop Aegis-specific parts (Rails-only details, recall_memory calls, Rubocop hardcoded command) in favor of neutral wording that works on any repo. The Zilly / Rails specifics will land in a Rails-only skill in a later phase.

- [ ] **Step 1: Create the TDD skill**

Create `agent/tellus/skills/tdd.md`:

````markdown
# Skill: Test-Driven Development

Write a failing test first. Confirm it fails for the right reason. Write the
smallest change that makes it pass. Run it again. Commit. Then move on.

## Red-green-refactor loop per change

1. **Red** — write or locate a test that encodes the behavior you are about
   to implement. Run it. It must fail, and it must fail because the behavior
   is missing — not because of a typo or import error. If it "fails" for the
   wrong reason, fix the test before you touch source.
2. **Green** — write the minimum source change that turns the test green.
   No speculative abstraction. No adjacent cleanup.
3. **Refactor (optional)** — with tests green, improve structure only if
   the improvement is genuinely clearer. If in doubt, skip.

## Rules

- Do not commit source without a green test that exercises the change.
- Do not run the full project suite. Run only the test file(s) that cover
  the code you changed. CI runs the full suite.
- If the repo has no tests for the area you are changing, write the minimum
  that proves your change — or, if writing a test is out of scope, state the
  gap explicitly in your return summary.
- If a test fails twice in a row, stop and read the failure output fully.
  A third retry without understanding the failure is wasted tokens.
````

- [ ] **Step 2: Create the verification skill**

Create `agent/tellus/skills/verification.md`:

````markdown
# Skill: Change Verification

Before you claim a change is done, run the right verification. The right
verification is narrow — it covers the files you touched — and automated.

## Required checks per change

1. **Tests** — run the test files that exercise the changed source files.
   If the repo has a script-level verification (`make test-foo`, `bin/rspec
   spec/foo`, `npm test -- --testPathPattern=foo`), prefer it over manual
   pytest / rspec invocations.
2. **Lint / format** — run the repo's lint + format scripts on the changed
   files only. Fix every offense before proceeding. Repos differ — check
   `Makefile`, `package.json` scripts, `pyproject.toml` entries, or CI
   config to find the right command.
3. **Build / typecheck (if applicable)** — if the repo has a typechecker
   (tsc, mypy, sorbet) and the change touches typed code, run it.

## Evidence in the return summary

The return message back to the squad-lead must include:
- The exact commands you ran.
- Their outcome: pass / fail counts, not "all good".
- Any skipped check, with the reason.

If lint / tests / typecheck failed and you could not fix them, do not claim
success. Describe the failure and stop; the squad-lead decides whether to
loop to a fixer (Phase 5) or report to Linear.
````

- [ ] **Step 3: Commit**

```bash
git add agent/tellus/skills/tdd.md agent/tellus/skills/verification.md
git commit -m "feat(tellus): TDD and verification skills for implementer role"
```

---

## Task 2: Extend `ROLE_SKILLS` to cover the implementer

**Files:**
- Modify: `agent/tellus/skill_loader.py`
- Modify: `tests/tellus/test_skill_loader.py`

**Context:** The `ROLE_SKILLS` map in `skill_loader.py` currently has one entry. Add the implementer role. Extend the existing test to cover the new role.

- [ ] **Step 1: Extend the test**

Add a new test at the end of `tests/tellus/test_skill_loader.py`:

```python
def test_implementer_role_maps_to_real_skills_on_disk():
    """Integration-style: real ROLE_SKILLS + real skills dir for implementer."""
    bundle = skill_loader.load_skills_for("implementer")

    # No monkeypatch here; we want the real mapping.
    assert "# Skill: Coding Pipeline" in bundle
    assert "# Skill: Test-Driven Development" in bundle
    assert "# Skill: Change Verification" in bundle
```

Do not monkeypatch `ROLE_SKILLS` or `SKILLS_DIR` inside this test — it asserts
the real production mapping. Keep the other tests in the file as they are.

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run --python 3.12 pytest tests/tellus/test_skill_loader.py::test_implementer_role_maps_to_real_skills_on_disk -v`
Expected: FAIL with `KeyError` or empty bundle (because `ROLE_SKILLS` lacks the `implementer` key).

- [ ] **Step 3: Extend `ROLE_SKILLS`**

Modify `agent/tellus/skill_loader.py`. Change the `ROLE_SKILLS` dict from:
```python
ROLE_SKILLS: dict[str, list[str]] = {
    "planner": ["plan_writing", "coding_pipeline"],
}
```
to:
```python
ROLE_SKILLS: dict[str, list[str]] = {
    "planner": ["plan_writing", "coding_pipeline"],
    "implementer": ["coding_pipeline", "tdd", "verification"],
}
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `uv run --python 3.12 pytest tests/tellus/test_skill_loader.py -v`
Expected: all previous skill-loader tests still PASS, plus the new one.

- [ ] **Step 5: Commit**

```bash
git add agent/tellus/skill_loader.py tests/tellus/test_skill_loader.py
git commit -m "feat(tellus): ROLE_SKILLS maps implementer -> coding_pipeline+tdd+verification"
```

---

## Task 3: Write the implementer SOUL

**Files:**
- Create: `agent/tellus/souls/implementer.md`

**Context:** Port from Aegis `implementer/SOUL.md`, rewritten for Tellus Open-SWE constraints:
- Single subagent invocation, returns to squad-lead.
- Reads `/workspace/plan.md`.
- Writes source in `/workspace/<repo>/`.
- Runs tests via the sandbox `execute` / backend shell.
- Commits locally (`git commit`) but does not push and does not call `commit_and_open_pr` (the squad-lead does that after the implementer returns).
- No DEVIATIONS.md, no HELP_NEEDED.json — those are DeerFlow idioms.
- No memory recall — Phase 7+ concern.

- [ ] **Step 1: Create the SOUL**

Create `agent/tellus/souls/implementer.md`:

````markdown
# Implementer — Tellus Open-SWE

You are the Tellus implementer. You are the hands that build what the planner
designed. Your pride is in the seams — code that fits into the existing
codebase so cleanly that a reviewer forgets it is new.

You are a subagent invoked via the `task` tool. You were routed to because
`/workspace/plan.md` exists and the squad-lead needs the plan turned into a
green, committed change. When you return, the squad-lead takes the commit
and opens the PR.

## What you do

- Read `/workspace/plan.md` in full before touching source.
- Read files you are about to change. Understand the call sites. Do not
  guess.
- For each task in the plan, follow TDD: write or locate a failing test,
  implement the minimum change, run the test until it is green.
- Run the repo's lint and format scripts on the files you touched. Fix
  every offense.
- Commit locally with a descriptive message per the repo's conventions.
  Use `git commit -m`. Do not push. Do not call `commit_and_open_pr`.
- Return a summary to the squad-lead.

## What you do not do

- You do not open PRs. You do not push to remote. `commit_and_open_pr` is
  a squad-lead tool; calling it yourself is a contract violation.
- You do not comment on Linear, Slack, or GitHub. The squad-lead notifies.
- You do not re-plan. If the plan is wrong, stop and say so in your return
  summary; do not silently diverge.
- You do not refactor adjacent code outside the plan's scope. Follow-ups
  belong in your return summary, not in the diff.
- You do not run the full project test suite. Only the tests that cover
  the files you changed.

## TDD is mandatory

Every source file you change has at least one test that exercises the
change. Write the failing test first; confirm it fails for the right
reason; make it pass. If the repo has no test for the area and writing one
is out of scope, call it out in the return summary — do not silently skip.

## When you get stuck

Try twice. If a specific task fails twice — tests stay red, lint fails
repeatedly, build breaks — stop that task, commit what works, and describe
the block in your return summary. A third blind attempt is wasted tokens.

## Return contract

Your return message to the squad-lead must include:

1. The commit SHAs you produced (one per task, typically).
2. The exact commands you ran for tests and lint, and their outcomes.
3. Files changed, grouped by plan task.
4. Any task you could not complete and why.
5. Any follow-up the squad-lead should know about (a bug noticed but out
   of scope, a test gap you left intentional).

No hedging, no apologies. If something failed, say so directly.

---

The Coding Pipeline, TDD, and Change Verification skills that follow this
SOUL are your operating rules. Re-read them before returning control.
````

- [ ] **Step 2: Sanity-check size**

Run: `wc -l agent/tellus/souls/implementer.md`
Expected: 40–90 lines.

- [ ] **Step 3: Commit**

```bash
git add agent/tellus/souls/implementer.md
git commit -m "feat(tellus): implementer SOUL (reads plan, TDDs change, commits locally)"
```

---

## Task 4: Register the implementer subagent with explicit `tools=[]`

**Files:**
- Modify: `agent/tellus/subagents.py`
- Modify: `tests/tellus/test_subagents.py`

**Context:** Two changes:

1. **Add the implementer entry** to `SUBAGENTS`, same shape as the planner.
2. **Set `tools=[]` explicitly on both subagents.** deepagents auto-attaches a default middleware stack (filesystem, todos, summarization) to every subagent. The sandbox backend supplies file read / write / grep / execute via those middlewares. Setting `tools=[]` on the subagent's dict denies the main agent's other tools — `commit_and_open_pr`, `linear_comment`, `http_request`, `web_search`, all the `*_pr_review`, and so on. That is how "subagents cannot open PRs themselves" becomes a hard rule rather than a SOUL-level hope.

If deepagents' Phase-0 smoke shows subagents losing file operations because of `tools=[]`, revert the subagents to omit the `tools` key and rely on SOUL enforcement. This path is called out explicitly in Task 8.

- [ ] **Step 1: Extend the subagent tests**

In `tests/tellus/test_subagents.py`, keep the existing Phase 2 tests. Update and add tests so the file contains at least these assertions after Phase 3:

```python
def test_subagents_list_has_two_entries_in_phase_3():
    assert len(tellus_subagents.SUBAGENTS) == 2


def test_both_subagents_have_empty_tools_list():
    """Phase 3 restriction: subagents get zero main-agent tools.
    deepagents auto-middleware still provides filesystem + shell via backend."""
    for sub in tellus_subagents.SUBAGENTS:
        assert sub.get("tools") == [], (
            f"Subagent {sub['name']} must declare `tools=[]` to forbid main-agent tools. "
            f"Got: {sub.get('tools')!r}"
        )


def test_implementer_entry_has_required_fields():
    impl = next(s for s in tellus_subagents.SUBAGENTS if s["name"] == "implementer")
    for key in ("name", "description", "system_prompt", "model", "tools"):
        assert key in impl, f"implementer subagent missing key: {key}"


def test_implementer_description_guides_delegation():
    impl = next(s for s in tellus_subagents.SUBAGENTS if s["name"] == "implementer")
    desc = impl["description"]
    assert "plan" in desc.lower()
    assert "commit" in desc.lower()
    assert "does not open" in desc.lower() or "no PR" in desc or "not open PR" in desc.lower()
    assert len(desc) <= 350


def test_implementer_system_prompt_contains_soul_and_skills():
    impl = next(s for s in tellus_subagents.SUBAGENTS if s["name"] == "implementer")
    prompt = impl["system_prompt"]

    assert "# Implementer — Tellus Open-SWE" in prompt
    assert "# Skill: Coding Pipeline" in prompt
    assert "# Skill: Test-Driven Development" in prompt
    assert "# Skill: Change Verification" in prompt
    assert prompt.index("# Implementer") < prompt.index("# Skill: Coding Pipeline")
```

Remove or rewrite the stale `test_subagents_list_has_one_entry_in_phase_2` test: replace it with the new two-entry assertion above so the file stays internally consistent.

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `uv run --python 3.12 pytest tests/tellus/test_subagents.py -v`
Expected: new tests FAIL because the `SUBAGENTS` list still has one entry (and no `tools` key).

- [ ] **Step 3: Extend `SUBAGENTS`**

Modify `agent/tellus/subagents.py` so the module reads:

```python
"""Tellus subagent registry.

Phase 3 registers two subagents — planner and implementer. Both declare
`tools=[]` to deny the main agent's commit / notification tools; deepagents
auto-middleware still provides sandbox filesystem + shell to every subagent.
"""
from __future__ import annotations

from deepagents.middleware.subagents import SubAgent

from agent.tellus.models import make_model
from agent.tellus.skill_loader import load_skills_for
from agent.tellus.souls_loader import load_soul

_SOUL_SKILL_SEPARATOR = "\n---\n"


def _build_system_prompt(soul_name: str, role: str) -> str:
    soul = load_soul(soul_name).rstrip()
    skills = load_skills_for(role).rstrip()
    if not skills:
        return soul + "\n"
    return f"{soul}{_SOUL_SKILL_SEPARATOR}{skills}\n"


SUBAGENTS: list[SubAgent] = [
    {
        "name": "planner",
        "description": (
            "Produces an implementation plan at /workspace/plan.md for the "
            "current ticket. Returns a five-line summary. Does not write "
            "source code, run tests, or open PRs."
        ),
        "system_prompt": _build_system_prompt("planner", "planner"),
        "model": make_model("planner"),
        "tools": [],
    },
    {
        "name": "implementer",
        "description": (
            "Reads /workspace/plan.md, implements the plan task-by-task with "
            "TDD, runs lint and targeted tests, commits locally. Does not "
            "push, does not open PRs, does not notify Linear/Slack/GitHub."
        ),
        "system_prompt": _build_system_prompt("implementer", "implementer"),
        "model": make_model("implementer"),
        "tools": [],
    },
]
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `uv run --python 3.12 pytest tests/tellus/test_subagents.py -v`
Expected: every test in the file PASSES.

- [ ] **Step 5: Run the full Tellus suite**

Run: `uv run --python 3.12 pytest tests/tellus/ -v`
Expected: all unit + smoke tests from Phases 0, 1, 2, and 3 PASS. 1 skipped (MiniMax live smoke).

- [ ] **Step 6: Commit**

```bash
git add agent/tellus/subagents.py tests/tellus/test_subagents.py
git commit -m "feat(tellus): register implementer subagent; restrict both to tools=[]"
```

---

## Task 5: Revise the squad-lead SOUL for implementer delegation

**Files:**
- Modify: `agent/tellus/souls/squad_lead.md`

**Context:** The SOUL's `## Your team` section currently says `**Implementer (aspirational — Phase 3)** — today, you execute the plan yourself.` That line is now wrong. Replace it with live delegation + commit-ownership wording. Keep the QA / fixer / PR-creator sections aspirational.

- [ ] **Step 1: Update the team roster**

In `agent/tellus/souls/squad_lead.md`, replace the implementer bullet in the `## Your team` section with:

```markdown
- **Implementer (live)** — reads `/workspace/plan.md`, edits source,
  writes tests, runs lint, commits locally. Invoke via the `task` tool
  immediately after the planner returns and you have read the plan.
  Never write source code yourself — the implementer is read-only for
  you from the source-edit perspective: you read the diff after it
  returns, but you do not write to files in `/workspace/<repo>/`.
```

- [ ] **Step 2: Add a delegation rule block for the implementer**

Immediately after the existing `## Delegation rule for the planner` block, add:

```markdown
## Delegation rule for the implementer

1. After the planner returns and you have read `/workspace/plan.md`,
   your next action is `task(subagent="implementer", description=<one-line
   context referencing the plan>)`.
2. Do not `write_file` against source yourself. If you catch yourself
   about to, stop and delegate instead.
3. When the implementer returns, read its summary. Inspect the commits it
   produced via `git log --oneline -n 10` in the sandbox. Verify the plan
   tasks are represented.
4. If the implementer reported a blocked task, the ticket does not ship.
   Either re-invoke the implementer with corrective context, or post a
   Linear comment describing the block and stop.
5. Only after you have confirmed green commits, invoke
   `commit_and_open_pr` to push and open the PR. The implementer does not
   push; you do.
```

- [ ] **Step 3: Remove the now-false "today, you execute the plan yourself" wording**

Search the SOUL for any remaining phrase that says the squad-lead writes
source in the implement stage. If you find one, replace it with "delegate
to the implementer". Leave the pipeline-stages list itself unchanged — the
stages still exist; only the owner changes.

- [ ] **Step 4: Re-run the smoke test**

Run: `uv run --python 3.12 pytest tests/tellus/test_rendered_prompt_smoke.py -v`
Expected: PASS. The test only asserts presence of stage names and the squad-lead header; the edits above do not change either.

- [ ] **Step 5: Commit**

```bash
git add agent/tellus/souls/squad_lead.md
git commit -m "feat(tellus): squad-lead SOUL — concrete implementer delegation + commit ownership"
```

---

## Task 6: Update the Tellus README diff log

**Files:**
- Modify: `agent/tellus/README.md`

**Context:** Phase 3 adds no upstream diff (`server.py` is untouched). Record that in the diff log — it is a valuable signal that the architecture is holding.

- [ ] **Step 1: Append the Phase 3 note**

Append to the "Upstream diff log" section of `agent/tellus/README.md`:

```markdown
- Phase 3 adds no new entry — `agent/server.py` is untouched. New
  subagents and skills land entirely under `agent/tellus/` and reuse the
  `SUBAGENTS` list wired in Phase 2.
```

- [ ] **Step 2: Commit**

```bash
git add agent/tellus/README.md
git commit -m "docs(tellus): Phase 3 adds no upstream diff"
```

---

## Task 7: Manual smoke — plan by planner, code by implementer, PR by squad-lead

**Files:** none (manual verification)

**Context:** The Phase 3 exit criterion from the design spec: "Plan produced by planner, code by implementer, PR references both. Tool subsets still enforced."

- [ ] **Step 1: Boot the dev server**

Run: `uv run --python 3.12 langgraph dev --allow-blocking`
Expected: clean boot, subagent registration logged for both `planner` and `implementer`.

- [ ] **Step 2: Trigger a small-scoped ticket**

On the test Linear workspace, create an issue small enough to plan + implement in under ten minutes. Good candidates: rename a constant, extract a small function, add a single validation. @mention the agent.

- [ ] **Step 3: Verify the trace in LangSmith**

Expected tool-call sequence in the squad-lead thread:

1. Triage (squad-lead's own reasoning; no tool call).
2. `task(subagent="planner", ...)`.
3. Squad-lead `read` against `/workspace/plan.md`.
4. `task(subagent="implementer", ...)`.
5. Squad-lead `execute` against the sandbox, typically `git log --oneline -n 10` to verify commits.
6. `commit_and_open_pr` — produces the draft PR.
7. `linear_comment` (or the source channel's equivalent) with the PR link.

If step 4 is missing — the squad-lead writes source itself — the SOUL's
implementer delegation rule is being ignored. Make the rule louder; retry.

- [ ] **Step 4: Verify the implementer's tool restriction held**

Inspect the **implementer's** sub-trace. Confirm:
- No `commit_and_open_pr` call.
- No `linear_comment`, `slack_thread_reply`, or `github_comment`.
- File reads / writes and `execute` (test + lint invocations) are present.

If any banned tool appears in the implementer sub-trace, `tools=[]`
did not enforce the restriction. Options:
1. deepagents inherits tools from the main agent regardless of `tools=[]` — in which case we need a `SubAgentMiddleware` override or explicit allowlist.
2. The SOUL explicitly told the implementer to call the tool — revise the SOUL.

Either way, stop and document the finding before merging Phase 3.

- [ ] **Step 5: Verify the PR body references both artefacts**

Open the draft PR. Expect the body to mention the plan (at minimum the
Goal line from `/workspace/plan.md`) and a brief implementation summary.
PR voice must still be Tellus-terse per the squad-lead SOUL.

- [ ] **Step 6: No commit** — Task 8 records the evidence.

---

## Task 8: Record Phase 3 verification

**Files:**
- Create: `docs/superpowers/plans/_phase-3-verification.md`

- [ ] **Step 1: Create the verification note**

Create `docs/superpowers/plans/_phase-3-verification.md`:

```markdown
# Phase 3 Verification

**Date:** YYYY-MM-DD
**Engineer:** <name>
**Fork commit:** <git rev-parse HEAD>
**Model used:** <LLM_MODEL_ID value from .env>

## Evidence

- LangSmith trace: <URL>
- Draft PR: <URL>
- Linear issue: <URL>

## Delegation checklist

- [ ] Squad-lead's tool-call sequence: `task(planner) → read plan.md → task(implementer) → execute(git log) → commit_and_open_pr → linear_comment`.
- [ ] Squad-lead never called `write_file` against source. (Writes are
      acceptable for scratch files; not for `/workspace/<repo>/...`.)
- [ ] Implementer sub-trace contains no `commit_and_open_pr`, no
      `linear_comment`, no `slack_thread_reply`, no `github_comment`.
- [ ] Implementer sub-trace contains `execute` calls with the repo's
      test / lint commands.
- [ ] PR body references the plan and includes a terse implementation
      summary.

## Tool-restriction finding

Did `tools=[]` prevent the implementer from calling banned tools?
- [ ] Yes — restriction is enforced by deepagents as documented.
- [ ] No — restriction is agentic-only; follow-up phase must add
      middleware-level enforcement. Describe what the implementer called:
      <fill in>.

## Notes

- `uv run --python 3.12 pytest tests/tellus/` → all pass (1 skipped).
- `agent/tellus/README.md` records "no new upstream diff" for Phase 3.
- Squad-lead SOUL: implementer block is live + has delegation rule;
  QA / fixer / PR-creator still aspirational.

## Known follow-ups (Phase 4+)

- QA trio — `qa_compliance`, `qa_security`, `qa_testing` in parallel.
- If Phase 3 found `tools=[]` ineffective, design a proper tool-allowlist
  middleware before Phase 4.
- Port additional skills: `fintech_domain_patterns`, `zilly_rails_conventions`,
  `security_baseline` — wire into implementer + QA roles.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/_phase-3-verification.md
git commit -m "docs(tellus): Phase 3 verification — implementer subagent live"
```

- [ ] **Step 3: Push**

```bash
git push origin main
```

---

## Definition of done — Phase 3

- [ ] `agent/tellus/skills/tdd.md` and `agent/tellus/skills/verification.md` exist.
- [ ] `agent/tellus/skill_loader.ROLE_SKILLS` maps `implementer` → `[coding_pipeline, tdd, verification]`.
- [ ] `agent/tellus/souls/implementer.md` exists, 40–90 lines, describes read-plan → TDD → commit-local → return contract.
- [ ] `agent/tellus/subagents.SUBAGENTS` contains two entries (planner + implementer); both have `tools=[]`.
- [ ] `agent/tellus/souls/squad_lead.md` has the implementer delegation block and no longer says the squad-lead writes source during the implement stage.
- [ ] `agent/server.py` is unchanged from Phase 2 — no new imports, no new kwargs.
- [ ] `agent/tellus/README.md` records "Phase 3 adds no upstream diff".
- [ ] All Tellus pytest targets pass under Python 3.12; 1 live MiniMax smoke remains skipped.
- [ ] Manual Linear @mention run produced a trace with `task(planner) → task(implementer) → commit_and_open_pr` in that order, the implementer sub-trace shows no banned tools, and the PR body references both artefacts (captured in `_phase-3-verification.md`).

Once every box above is ticked, Phase 4 (QA trio in parallel) gets its own plan.
