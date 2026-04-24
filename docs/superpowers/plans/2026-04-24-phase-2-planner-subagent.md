# Phase 2 — Planner Subagent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce the first specialist subagent — the planner — to the Tellus Open-SWE deep agent. The squad-lead will delegate planning to the planner via the `task` tool. The planner writes its plan to `/workspace/plan.md` in the sandbox. Squad-lead reads that plan before coding. Every other pipeline stage (implement, QA, fixer, PR) still runs inside the squad-lead for now.

**Architecture:** Add `agent/tellus/subagents.py` with a `SUBAGENTS` list containing one `SubAgent` TypedDict for the planner. Add `agent/tellus/skill_loader.py` with a static role→skills map. Port two Aegis skills (plan_writing, coding_pipeline) into `agent/tellus/skills/`. Write `agent/tellus/souls/planner.md`. Revise `agent/tellus/souls/squad_lead.md` to replace "aspirational roster" with concrete planner-delegation rules. Add a third line to `agent/server.py`: `subagents=SUBAGENTS,` inside the existing `create_deep_agent(...)` call, plus the matching import.

**Tech Stack:** Python 3.12, `deepagents.middleware.subagents.SubAgent` TypedDict, LangSmith Sandbox backend. No new third-party deps.

**Pre-requisites:**
- Phase 1 complete: `agent/tellus/souls/squad_lead.md`, `agent/tellus/prompt.py`, `agent/tellus/souls_loader.py`, `agent/server.py` pointing at Tellus prompt.
- `origin/main` at `45d713c4` or later.
- MiniMax still the sole model provider; no per-role model overrides in Phase 2.

**Non-goals:**
- Explicit tool-subset enforcement on the planner (planner inherits the main agent's tool list; read-only behavior is prompt-enforced via SOUL). Tool restriction comes in Phase 3 once we see how deepagents resolves inherited vs. declared tools in practice.
- QA, fixer, implementer, PR-creator subagents — Phases 3, 4, 5.
- Hard gates on plan quality — not in v1.
- Skill injection via deepagents' native `skills` parameter (its loader expects a path format we haven't vetted). We inject skills by concatenating them into the subagent's `system_prompt` string.

---

## File Structure

**New files (all under `agent/tellus/`):**

| File | Responsibility |
|---|---|
| `agent/tellus/skills/__init__.py` | Package marker. Empty. |
| `agent/tellus/skills/plan_writing.md` | Ported from Aegis's `skills/custom/plan-writing/SKILL.md`, trimmed to runtime-relevant guidance. |
| `agent/tellus/skills/coding_pipeline.md` | Ported from Aegis's `skills/custom/coding-pipeline/SKILL.md`. |
| `agent/tellus/skill_loader.py` | `load_skills_for(role) -> str` — reads the role→skills map and returns concatenated markdown ready to append to a system prompt. Raises on missing skill files. |
| `agent/tellus/subagents.py` | `SUBAGENTS: list[SubAgent]` — Phase 2 contains only the planner entry. Composes SOUL + injected skills into `system_prompt`. |
| `agent/tellus/souls/planner.md` | Tellus planner SOUL — single-purpose, writes `/workspace/plan.md`, returns a terse summary to the lead. |
| `tests/tellus/test_skill_loader.py` | Unit tests for `skill_loader`. |
| `tests/tellus/test_subagents.py` | Unit tests for the `SUBAGENTS` list (shape, SOUL embedded, skills embedded). |
| `tests/tellus/fixtures/skills/alpha.md` | 3-line fixture skill used by loader tests. |
| `tests/tellus/fixtures/skills/beta.md` | 3-line fixture skill. |

**Modified files:**

| File | Change |
|---|---|
| `agent/server.py` | Two more lines: `from .tellus.subagents import SUBAGENTS` at the top and `subagents=SUBAGENTS,` inside `create_deep_agent(...)`. |
| `agent/tellus/souls/squad_lead.md` | Replace "aspirational roster" paragraph + Phase 1 "you play every role yourself" wording with explicit planner-delegation rules. Other roles remain aspirational. |
| `agent/tellus/README.md` | Append Phase 2 diff-log entries. |

**Untouched:** every other upstream file.

---

## Task 1: Add the skill library and loader

**Files:**
- Create: `agent/tellus/skills/__init__.py`
- Create: `agent/tellus/skills/plan_writing.md`
- Create: `agent/tellus/skills/coding_pipeline.md`
- Create: `agent/tellus/skill_loader.py`
- Test: `tests/tellus/test_skill_loader.py`
- Create: `tests/tellus/fixtures/skills/__init__.py`
- Create: `tests/tellus/fixtures/skills/alpha.md`
- Create: `tests/tellus/fixtures/skills/beta.md`

**Context:** `load_skills_for(role)` accepts a role name (e.g. `"planner"`) and returns a single markdown blob: the concatenation of the skill files mapped to that role, each preceded by its skill heading. The blob is designed to be appended to a subagent's `system_prompt`. Missing skill files raise `SkillNotFound` (subclass of `FileNotFoundError`) so a typo in the role map fails loud instead of silently shrinking the prompt.

- [ ] **Step 1: Write the failing tests**

Create `tests/tellus/fixtures/skills/__init__.py`:
```python
```

Create `tests/tellus/fixtures/skills/alpha.md`:
```markdown
# Alpha skill

Alpha instruction one.
Alpha instruction two.
```

Create `tests/tellus/fixtures/skills/beta.md`:
```markdown
# Beta skill

Beta instruction one.
```

Create `tests/tellus/test_skill_loader.py`:
```python
"""Unit tests for agent.tellus.skill_loader."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent.tellus import skill_loader


@pytest.fixture
def fixture_skills(monkeypatch):
    fixture_dir = Path(__file__).parent / "fixtures" / "skills"
    monkeypatch.setattr(skill_loader, "SKILLS_DIR", fixture_dir)
    monkeypatch.setattr(
        skill_loader,
        "ROLE_SKILLS",
        {"planner": ["alpha", "beta"], "implementer": ["alpha"]},
    )
    return fixture_dir


def test_load_skills_for_returns_concatenated_markdown(fixture_skills):
    bundle = skill_loader.load_skills_for("planner")

    assert "Alpha skill" in bundle
    assert "Beta skill" in bundle
    # Alpha must appear before Beta (map order is respected)
    assert bundle.index("Alpha skill") < bundle.index("Beta skill")
    # Skills are separated by a blank line so the LLM sees them as distinct blocks
    assert "\n\n# Beta skill" in bundle


def test_load_skills_for_unknown_role_returns_empty_string(fixture_skills):
    assert skill_loader.load_skills_for("unknown_role") == ""


def test_load_skills_for_missing_skill_file_raises(fixture_skills, monkeypatch):
    monkeypatch.setattr(
        skill_loader, "ROLE_SKILLS", {"planner": ["alpha", "missing_one"]}
    )
    with pytest.raises(skill_loader.SkillNotFound) as excinfo:
        skill_loader.load_skills_for("planner")
    assert "missing_one" in str(excinfo.value)


def test_skill_not_found_is_a_file_not_found_subclass():
    assert issubclass(skill_loader.SkillNotFound, FileNotFoundError)
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run --python 3.12 pytest tests/tellus/test_skill_loader.py -v`
Expected: all four tests FAIL with `ModuleNotFoundError: No module named 'agent.tellus.skill_loader'`.

- [ ] **Step 3: Implement the skill library files**

Create `agent/tellus/skills/__init__.py`:
```python
```

Create `agent/tellus/skills/plan_writing.md`:
````markdown
# Skill: Plan Writing

Write plans that tell the implementer WHAT and WHY — never HOW. Method
signatures, query strategies, test body contents belong to the implementer.

## Plan file format

Save to `/workspace/plan.md` in the sandbox. One plan file per ticket.

```markdown
# <ISSUE_ID>: <TITLE> — Implementation Plan

**Goal:** One sentence — desired end state once all tasks complete.
**Architecture:** 2–3 sentences on approach. Name the file groups touched.
**Tech Stack:** The actual languages / frameworks the repo uses.

---

### Task N: <what this accomplishes>

**Goal:** One sentence — desired behavior change.
**Scope:** Exact file paths that will be touched and their test files.
**Constraints:** Backward-compatibility, existing-pattern requirements,
performance / security requirements. No method names, no SQL, no test
body descriptions.
**Depends on:** Task M, or "none".
**Success criteria:** Observable, verifiable outcomes — a shell command
that exits 0, a test name that passes, an HTTP response shape. Bad:
"endpoint works". Good: "GET /api/x returns 200 with field y".
**Commit:** `<type>(<ISSUE_ID>): <what this task accomplishes>`
**Estimated minutes:** N. If >30, decompose into sub-tasks that each
fit within 30.
```

## Self-validation before returning the plan

Before returning control to the squad-lead, confirm each of the following:

1. Every file path referenced in `Scope` is reachable from `/workspace/<repo>/`.
2. Every success criterion starts with an executable verification — a test
   command, a curl invocation, or an HTTP response assertion.
3. Every task has `estimated_minutes <= 30`.
4. The plan contains no method signatures, no SQL fragments, no prescribed
   test body text.

If any check fails, revise the plan before returning.

## Scope discipline

Scope is only what the ticket requires (YAGNI). If you discover adjacent
issues, note them at the end of the plan in a `## Follow-ups` section and
do not include them as tasks.
````

Create `agent/tellus/skills/coding_pipeline.md`:
````markdown
# Skill: Coding Pipeline

Every ticket passes through the same stages. Name the stage you are in
before you act in it. Never skip.

1. **Triage** — Classify: bug, feature, refactor, infra, docs. Identify
   the target repo and the affected module. If the ticket is ambiguous,
   ask a focused question in the source channel and stop.
2. **Plan** — Produce a written plan (see the Plan Writing skill).
3. **Sanity-check the plan** — Re-read. Is it addressing the real root
   cause? Would a senior colleague accept it? Shrink if it overreaches.
4. **Implement** — Make the minimal change. Do not refactor adjacent code
   that the ticket does not require. Keep the diff focused.
5. **Self-QA** — Compliance (scope + AGENTS.md), security (secrets, auth,
   PII, injection), testing (run tests that exercise the changed code).
6. **Submit** — Call `commit_and_open_pr` with a draft PR. Title under 70
   chars, body under 10 lines, include a Test Plan section with
   novel verification steps only.
7. **Notify** — Post a Linear / Slack / GitHub comment that @-mentions the
   requester and links the PR.

## Pipeline rules

- Plan before code. No `write_file` against source before a plan exists.
- Do not widen scope mid-ticket. Follow-ups go in the PR body, not in
  the commit.
- Never commit secrets. If one would be needed, stop and ask for a vault
  reference.
- Respect `AGENTS.md`. If it conflicts with anything else, AGENTS.md wins.
````

- [ ] **Step 4: Implement the loader**

Create `agent/tellus/skill_loader.py`:
```python
"""Skill loader.

Maps a subagent role to a list of skill names; returns the concatenated
markdown content of those skills ready for appending to a subagent's
`system_prompt`. Unknown roles return the empty string (no skills injected).
Missing skill files raise `SkillNotFound` so typos in `ROLE_SKILLS` fail
loud at registration time.
"""
from __future__ import annotations

from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent / "skills"

# Role -> ordered list of skill names (file stems under SKILLS_DIR).
# Phase 2 covers the planner only; later phases extend this map.
ROLE_SKILLS: dict[str, list[str]] = {
    "planner": ["plan_writing", "coding_pipeline"],
}


class SkillNotFound(FileNotFoundError):
    """Raised when a skill file referenced in ROLE_SKILLS is missing."""


def load_skills_for(role: str) -> str:
    """Return concatenated skill markdown for a role, or empty if unknown."""
    skill_names = ROLE_SKILLS.get(role)
    if not skill_names:
        return ""

    parts: list[str] = []
    for name in skill_names:
        path = SKILLS_DIR / f"{name}.md"
        try:
            parts.append(path.read_text().rstrip())
        except FileNotFoundError as exc:
            raise SkillNotFound(
                f"Skill '{name}' not found at {path}. "
                f"Referenced by ROLE_SKILLS[{role!r}]."
            ) from exc

    return "\n\n".join(parts) + "\n"
```

- [ ] **Step 5: Run tests to confirm they pass**

Run: `uv run --python 3.12 pytest tests/tellus/test_skill_loader.py -v`
Expected: all four tests PASS.

- [ ] **Step 6: Commit**

```bash
git add agent/tellus/skills/ agent/tellus/skill_loader.py \
        tests/tellus/test_skill_loader.py \
        tests/tellus/fixtures/skills/
git commit -m "feat(tellus): skill loader + plan_writing & coding_pipeline skills"
```

---

## Task 2: Write the planner SOUL

**Files:**
- Create: `agent/tellus/souls/planner.md`

**Context:** The planner is a one-job subagent: produce a self-validated plan at `/workspace/plan.md`, return a terse summary to the squad-lead. It does not code, it does not commit, it does not comment on Linear. It reads the repo, reads any existing plan, and writes one.

The SOUL below is written for Phase 2's constraints:
- Single file artifact: `/workspace/plan.md`.
- No subagents of its own.
- No explicit tool restriction — SOUL tells it to avoid code edits and commits.

- [ ] **Step 1: Create the SOUL**

Create `agent/tellus/souls/planner.md`:

````markdown
# Planner — Tellus Open-SWE

You are the Tellus planner. Your job is to turn one Linear ticket into one
implementation plan saved to `/workspace/plan.md` in the sandbox, and
return a terse summary to your squad-lead.

You are a subagent invoked via the `task` tool. The squad-lead routed work
to you because the ticket has not been planned yet. When you return, the
squad-lead reads `/workspace/plan.md` and continues from there.

## What you do

- Read the ticket and any linked context the squad-lead gave you.
- Explore the target repository read-only. Use search tools to locate the
  affected files. Read them. Trace calls as far as necessary to understand
  the blast radius.
- Write a plan to `/workspace/plan.md`. Overwrite any existing plan.md.
- Return a five-line summary to the squad-lead: one line per stage (goal,
  scope, key risks, verification, estimated minutes total).

## What you do not do

- You do not write source code. Only `/workspace/plan.md`.
- You do not run the test suite. You may run `grep`, `ls`, `cat` — anything
  read-only — to understand the code. You do not run builds.
- You do not open PRs. You do not comment on Linear. You do not invoke
  subagents. Those are squad-lead responsibilities.
- You do not claim to have planned anything you have not verified against
  real files in the repo. If a file you referenced does not exist, fix the
  plan before returning.

## Tone

Concise, direct, no hedging. If the ticket is ambiguous, write the plan
around the narrowest defensible interpretation and name the ambiguity in a
`## Open questions` section at the bottom — do not stop and ask.

## Output contract

- `/workspace/plan.md` exists and passes the self-validation rules from the
  Plan Writing skill.
- Your return message to the squad-lead names the file path, total estimated
  minutes, and the single biggest risk. No more than five lines.

Example return message:

```
Plan: /workspace/plan.md
Scope: 3 tasks, 55 min total, auth service + spec update.
Risk: token refresh timer is shared across contexts; retest concurrency.
```

---

The Plan Writing and Coding Pipeline skills that follow this SOUL are your
operating rules. Re-read them before returning control.
````

- [ ] **Step 2: Sanity-check file size**

Run: `wc -l agent/tellus/souls/planner.md`
Expected: 35–80 lines.

- [ ] **Step 3: Commit**

```bash
git add agent/tellus/souls/planner.md
git commit -m "feat(tellus): planner SOUL (writes plan.md, returns summary)"
```

---

## Task 3: Register the planner subagent

**Files:**
- Create: `agent/tellus/subagents.py`
- Test: `tests/tellus/test_subagents.py`

**Context:** `SUBAGENTS` is a list of `deepagents.middleware.subagents.SubAgent` TypedDicts. For Phase 2 the list holds exactly one entry — the planner. The entry's `system_prompt` is the planner SOUL **plus** the planner-role skill bundle, joined by a separator. The planner gets its own model via `make_model("planner")` (falls back to default MiniMax).

We omit the subagent's `tools` field on purpose. deepagents documents that an omitted `tools` list makes the subagent inherit the main agent's tools. Explicit tool restriction is a Phase 3 concern.

- [ ] **Step 1: Write the failing tests**

Create `tests/tellus/test_subagents.py`:
```python
"""Unit tests for agent.tellus.subagents."""
from __future__ import annotations

import pytest

from agent.tellus import subagents as tellus_subagents


def test_subagents_list_has_one_entry_in_phase_2():
    assert len(tellus_subagents.SUBAGENTS) == 1


def test_planner_entry_has_required_fields():
    planner = next(s for s in tellus_subagents.SUBAGENTS if s["name"] == "planner")

    for key in ("name", "description", "system_prompt", "model"):
        assert key in planner, f"planner subagent missing key: {key}"


def test_planner_description_guides_delegation():
    planner = next(s for s in tellus_subagents.SUBAGENTS if s["name"] == "planner")
    # The main agent sees `description` when deciding whether to delegate.
    # Must be short, action-oriented, and mention the one artifact.
    desc = planner["description"]
    assert "plan" in desc.lower()
    assert "/workspace/plan.md" in desc
    assert len(desc) <= 250


def test_planner_system_prompt_contains_soul_and_skills():
    planner = next(s for s in tellus_subagents.SUBAGENTS if s["name"] == "planner")
    prompt = planner["system_prompt"]

    # SOUL header
    assert "# Planner — Tellus Open-SWE" in prompt
    # Skills must be appended, not replaced
    assert "# Skill: Plan Writing" in prompt
    assert "# Skill: Coding Pipeline" in prompt
    # SOUL appears before skills
    assert prompt.index("# Planner") < prompt.index("# Skill: Plan Writing")


def test_missing_soul_fails_loudly_at_import(monkeypatch, tmp_path):
    """If anyone renames planner.md without updating subagents.py, we want a
    loud error at import rather than a silent empty persona."""
    from importlib import reload

    from agent.tellus import souls_loader

    monkeypatch.setattr(souls_loader, "SOULS_DIR", tmp_path)

    with pytest.raises(souls_loader.SoulNotFound):
        reload(tellus_subagents)
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run --python 3.12 pytest tests/tellus/test_subagents.py -v`
Expected: all five tests FAIL with `ModuleNotFoundError: No module named 'agent.tellus.subagents'`.

- [ ] **Step 3: Implement the subagent registry**

Create `agent/tellus/subagents.py`:
```python
"""Tellus subagent registry.

Phase 2 registers exactly one subagent — the planner. Later phases extend
this list with implementer, QA trio, fixer, etc.
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
    },
]
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `uv run --python 3.12 pytest tests/tellus/test_subagents.py -v`
Expected: all five tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/tellus/subagents.py tests/tellus/test_subagents.py
git commit -m "feat(tellus): register planner subagent with SOUL + injected skills"
```

---

## Task 4: Wire `SUBAGENTS` into `agent/server.py`

**Files:**
- Modify: `agent/server.py`

**Context:** `create_deep_agent` accepts `subagents=[...]`. We add the import and one keyword argument. No other changes.

- [ ] **Step 1: Read the current imports block in server.py**

Run: `grep -n "^from \.tellus" agent/server.py`
Expected:
```
35:from .tellus.models import make_model
36:from .tellus.prompt import construct_system_prompt
```

- [ ] **Step 2: Add the subagents import**

Insert a new line directly after line 36:

```python
from .tellus.subagents import SUBAGENTS
```

- [ ] **Step 3: Verify the new import**

Run: `grep -n "^from \.tellus" agent/server.py`
Expected:
```
35:from .tellus.models import make_model
36:from .tellus.prompt import construct_system_prompt
37:from .tellus.subagents import SUBAGENTS
```

- [ ] **Step 4: Add `subagents=SUBAGENTS,` to the `create_deep_agent(...)` call**

Locate the `return create_deep_agent(` block inside `get_agent` (currently starting around line 277). Add `subagents=SUBAGENTS,` immediately before the `middleware=[...]` argument. After the change the call should look like (abbreviated):

```python
return create_deep_agent(
    model=make_model(os.environ.get("LLM_MODEL_ID", DEFAULT_LLM_MODEL_ID), max_tokens=20_000),
    system_prompt=construct_system_prompt(
        working_dir=work_dir,
        linear_project_id=linear_project_id,
        linear_issue_number=linear_issue_number,
    ),
    tools=[ ... ],
    backend=sandbox_backend,
    subagents=SUBAGENTS,
    middleware=[
        ToolErrorMiddleware(),
        check_message_queue_before_model,
        ensure_no_empty_msg,
        open_pr_if_needed,
    ],
).with_config(config)
```

- [ ] **Step 5: Sanity-check the single call site**

Run: `grep -n "subagents=" agent/server.py`
Expected: exactly one line, referencing `SUBAGENTS`.

- [ ] **Step 6: Run every Tellus test**

Run: `uv run --python 3.12 pytest tests/tellus/ -v`
Expected: all unit + smoke tests from Phases 0, 1, and 2 PASS. 1 skipped (MiniMax live smoke).

- [ ] **Step 7: Commit**

```bash
git add agent/server.py
git commit -m "chore(tellus): wire SUBAGENTS into create_deep_agent"
```

---

## Task 5: Revise the squad-lead SOUL for planner delegation

**Files:**
- Modify: `agent/tellus/souls/squad_lead.md`

**Context:** Phase 1's SOUL said "aspirational — Phase 1 has no delegation; you play every role yourself." With the planner live, that sentence is now wrong for the planning stage. Replace it with explicit delegation rules for the planner only. Every other role stays aspirational.

- [ ] **Step 1: Locate the section to replace**

The SOUL currently contains a section `## Your team (aspirational — Phase 1 has no delegation)` followed by a bulleted roster. Replace the whole block (header + bullets) with the updated block below. Leave everything else in the SOUL untouched.

- [ ] **Step 2: Apply the replacement**

Replace that block with:

```markdown
## Your team

You coordinate a team of specialist subagents. As of Phase 2, only one is
wired in. When you reach the planning stage, you **must** delegate by
invoking `task(subagent="planner", description=<short context>)`. Wait for
it to return, then read `/workspace/plan.md` before any further action.

- **Planner (live)** — turns a ticket into `/workspace/plan.md`. Invoke
  via the `task` tool. Never skip planning. Never write code before the
  planner returns.
- **Implementer (aspirational — Phase 3)** — today, you execute the plan
  yourself.
- **QA trio — compliance / security / testing (aspirational — Phase 4)** —
  today, you review your own change under all three lenses, in order.
- **Fixer (aspirational — Phase 5)** — today, you loop yourself if QA
  fails.
- **PR-creator** — today, you open the PR directly via `commit_and_open_pr`.

## Delegation rule for the planner

1. Once triage is complete, your very next action is `task(subagent="planner", ...)`.
2. Do not run `grep`, `read`, or any source-inspection tool before delegating —
   the planner does that inside its own isolated context.
3. When the planner returns, read `/workspace/plan.md` in full before making
   any code change.
4. If the plan is wrong, invoke the planner a second time with a correction
   prompt. Do not start implementation with a plan you disagree with.
```

- [ ] **Step 3: Confirm the rendered prompt still works**

Run: `uv run --python 3.12 pytest tests/tellus/test_rendered_prompt_smoke.py -v`
Expected: PASS. The existing smoke test already asserts that the seven pipeline stages appear; the section rename only touches the roster paragraph, not the stages list.

- [ ] **Step 4: Commit**

```bash
git add agent/tellus/souls/squad_lead.md
git commit -m "feat(tellus): squad-lead SOUL — concrete planner delegation rules"
```

---

## Task 6: Update the Tellus README diff log

**Files:**
- Modify: `agent/tellus/README.md`

- [ ] **Step 1: Append the new diff entries**

Append to the "Upstream diff log" section in `agent/tellus/README.md`:

```markdown
- `from .tellus.subagents import SUBAGENTS` (Phase 2)
- `subagents=SUBAGENTS,` argument inside `create_deep_agent(...)` (Phase 2)
```

Also update the running line count statement at the top of the section: change `the diff is two lines` to `the diff is four lines`.

- [ ] **Step 2: Commit**

```bash
git add agent/tellus/README.md
git commit -m "docs(tellus): record Phase 2 upstream diff entries"
```

---

## Task 7: Manual smoke — planner runs, plan.md exists in sandbox

**Files:** none (manual verification)

**Context:** The Phase 2 exit criterion from the design spec: "Ticket → squad-lead invokes planner via `task`; `plan.md` appears in sandbox; lead references it when coding." Automated assertion is hard because the plan path is inside the LangSmith sandbox; verification is visual via the LangSmith trace + a follow-up `execute` on the sandbox to `cat /workspace/plan.md`.

- [ ] **Step 1: Boot the dev server**

Run: `uv run --python 3.12 langgraph dev --allow-blocking`
Expected: clean boot, no tracebacks. Check for an info log mentioning the planner subagent registration (deepagents typically logs registered subagents).

- [ ] **Step 2: Trigger a Linear ticket**

Create a small-scoped Linear ticket on the test workspace. Title: `Phase 2 smoke: rename a constant in the playground repo`. Body: a one-paragraph description naming the constant and the new name. @mention the agent.

- [ ] **Step 3: Inspect the trace in LangSmith**

Open the thread. Expectations:
1. The **first model call** system prompt starts with `# Squad-Lead — Tellus Open-SWE` and contains the updated `## Delegation rule for the planner` block.
2. The squad-lead's first tool call is `task` with `subagent="planner"`.
3. The planner's sub-trace contains at least one `read` / `grep` call, one `write` call targeting `/workspace/plan.md`, and ends by returning a short text message to the parent.
4. The squad-lead's second tool call is `read` against `/workspace/plan.md`.
5. The squad-lead then performs the code change, commits, and opens a PR.

If step 2 does not happen — the lead goes straight to `read` or `grep` without invoking `task` — the SOUL delegation rule is being ignored. Revise the squad-lead SOUL wording to make the rule louder before retrying.

- [ ] **Step 4: Inspect `/workspace/plan.md` in the sandbox**

From the LangSmith trace, find a turn where the squad-lead ran `execute` or `read` against the sandbox and confirm `/workspace/plan.md` exists. If the plan file is present and matches the Plan Writing skill format (Goal, Architecture, tasks, Success criteria), Phase 2's artifact contract is satisfied.

- [ ] **Step 5: No commit** — Task 8 records the verification.

---

## Task 8: Record Phase 2 verification

**Files:**
- Create: `docs/superpowers/plans/_phase-2-verification.md`

- [ ] **Step 1: Create the verification note**

Create `docs/superpowers/plans/_phase-2-verification.md`:

```markdown
# Phase 2 Verification

**Date:** YYYY-MM-DD
**Engineer:** <name>
**Fork commit:** <git rev-parse HEAD>
**Model used:** <LLM_MODEL_ID value from .env>

## Evidence

- LangSmith trace: <URL>
- Draft PR: <URL>
- Linear issue: <URL>

## Planner behavior checklist

- [ ] Squad-lead's first non-triage tool call was `task(subagent="planner", ...)`.
- [ ] Planner sub-trace wrote `/workspace/plan.md`.
- [ ] Plan file contains Goal / Architecture / at least one numbered Task /
      each Task has Scope, Constraints, Success criteria.
- [ ] Planner returned a ≤ 5-line summary to the squad-lead.
- [ ] Squad-lead read `/workspace/plan.md` before writing code.

## Notes

- `uv run --python 3.12 pytest tests/tellus/` → all pass (1 skipped).
- `agent/tellus/README.md` upstream-diff log lists four entries.
- Squad-lead SOUL no longer says "you play every role yourself" — planner
  block was replaced with concrete delegation rule.

## Known follow-ups (Phase 3+)

- Implementer subagent (Phase 3). Squad-lead stops writing source itself.
- Explicit tool subsets per subagent once deepagents tool-inheritance
  behavior is confirmed in practice.
- Port additional skills (fintech_domain_patterns, zilly_rails_conventions,
  tdd, security_baseline).
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/_phase-2-verification.md
git commit -m "docs(tellus): Phase 2 verification — planner subagent live"
```

- [ ] **Step 3: Push**

```bash
git push origin main
```

---

## Definition of done — Phase 2

- [ ] `agent/tellus/skills/` contains `plan_writing.md` and `coding_pipeline.md`.
- [ ] `agent/tellus/skill_loader.py` exists with `ROLE_SKILLS`, `load_skills_for`, `SkillNotFound`.
- [ ] `agent/tellus/souls/planner.md` exists, 35–80 lines.
- [ ] `agent/tellus/subagents.py` exposes `SUBAGENTS` with one planner entry whose `system_prompt` contains both the SOUL and the injected skills.
- [ ] `agent/server.py` has three `from .tellus.*` imports and one `subagents=SUBAGENTS,` argument inside `create_deep_agent(...)`.
- [ ] `agent/tellus/souls/squad_lead.md` has the new `## Your team` + `## Delegation rule for the planner` block (Phase 1 "aspirational roster" wording removed for the planner only).
- [ ] `agent/tellus/README.md` records the Phase 2 diff entries.
- [ ] All Tellus pytest targets pass under Python 3.12; 1 live MiniMax smoke remains skipped.
- [ ] Manual Linear @mention run produced a sandbox with `/workspace/plan.md` written by the planner subagent and consumed by the squad-lead (captured in `_phase-2-verification.md`).

Once every box above is ticked, Phase 3 (implementer subagent) gets its own plan.
