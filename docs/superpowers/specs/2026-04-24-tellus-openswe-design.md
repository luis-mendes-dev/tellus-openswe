# Tellus Open-SWE — Design Spec

**Date:** 2026-04-24
**Owner:** Luis Miguel Mendes (CTO, Tellus)
**Status:** Pending user review of written spec
**Scope:** v1 = Phases 0–5 (happy path). Phases 6–8 each get their own design + plan later.
**Supersedes:** Tellus Aegis (to be retired after Tellus Open-SWE reaches parity at Phase 5)

## Goal

Build a Tellus-owned, async, autonomous coding agent — the functional equivalent of Google Jules — on top of a fork of [langchain-ai/open-swe](https://github.com/langchain-ai/open-swe). Retain every capability unique to Tellus Aegis (SOULs, pipeline stages, skills, and — in later phases — self-learning and institutional memory). Replace the DeerFlow harness with Open-SWE's LangGraph + Deep Agents runtime.

## Non-goals (v1 happy path)

- Human-in-the-loop approval gates. Explicitly rejected.
- Hard Python-enforced quality gates (plan_eval score ≥ 8, QA composite). Deferred to post-v1; design leaves insertion points.
- Multi-repo support beyond `zilly-backend`.
- Aegis operations dashboard UI — replaced later by a thin new dashboard.
- SOUL evolution / learning feedback loop — Phase 6+ (data capture only, no active learning in v1).

## Context

**Tellus Aegis** is Tellus's current autonomous engineering pipeline. It sits on **DeerFlow** (ByteDance's open-source LangGraph harness). Aegis owns:

- Pipeline stages (`triage → plan → plan_eval → impl → qa → fixer → pr`)
- Curated SOULs for each specialist agent (planner, implementer, qa-lead, qa-security, qa-compliance, qa-testing, fixer, pr-creator, squad-lead, plus learning agents)
- Domain skills (fintech patterns, Zilly Rails conventions, Plaid integration, security baseline, etc.)
- Learning pipeline (post-mortem → soul synthesis) — currently a separate LangGraph sidecar
- Institutional memory (SQLite: Issue, AgentSession, Decision, RunOutcome)
- Ops dashboard

**Open-SWE** (current `main`, Python rewrite) is a single deep-agent built on `deepagents.create_deep_agent(...)` that runs inside a per-thread sandbox. It provides:

- Linear, Slack, and GitHub webhook entrypoints (`agent/webapp.py`)
- Pluggable sandbox backends (LangSmith Sandbox default, Daytona, Modal, Runloop, Local)
- GitHub App auth via a LangSmith HTTP proxy (no token on disk)
- Deterministic thread IDs from issue/thread source (Linear issue, Slack thread, GitHub issue)
- Native `task` tool for subagent fan-out
- Middleware hooks: `@before_model`, `@after_agent`, `@after_subagent`
- `commit_and_open_pr` tool and `open_pr_if_needed` after-agent safety net

Open-SWE intentionally has **no HITL interrupts** and **no gates**. It uses a message queue (`check_message_queue_before_model`) so operators can nudge a running agent via Linear/Slack comments.

## Key decisions (from brainstorming)

| Decision | Choice | Rationale |
|---|---|---|
| Relationship to Open-SWE | Fork + upstream tracking | Receive upstream improvements; isolate Tellus code under `agent/tellus/` to keep merges clean |
| Architecture shape | Bottom-up, β: single squad-lead deep-agent + subagents via `task` | Matches Open-SWE grain; dev-team metaphor maps naturally; subagent context isolation scales |
| Number of agents | Multi-agent team (squad-lead + planner + implementer + qa_compliance + qa_security + qa_testing + fixer) | Mirrors Aegis; each subagent = team member with own SOUL + tool subset |
| Gate enforcement | Agentic first, thin Python safety nets later | Matches Open-SWE grain; user explicitly chose happy path v1 with no gates |
| HITL | None | User explicitly rejected approval gates |
| Model provider | MiniMax for everything (single provider via `make_model`) | User choice; `make_model` stays pluggable for later per-role overrides |
| Language | Python 3.12 | Matches Open-SWE and Aegis |
| Sandbox | LangSmith Sandbox default, pluggable | Open-SWE default; Daytona/Modal available without code changes |
| Domain DB | Separate Postgres/SQLite outside LangGraph, wired in Phase 6 | Preserves Aegis's RunOutcome pattern without polluting checkpoint |

## Architecture

### Runtime shape

```
Linear webhook
    │
    ▼
FastAPI webapp  (Open-SWE, unchanged)
    │  generate_thread_id_from_issue → deterministic
    ▼
LangGraph thread (checkpointed, per-ticket sandbox cached)
    │
    ▼
Squad-lead deep-agent  (Tellus SOUL)
    │ invokes via task tool
    ├── planner        (read-only tools)
    ├── implementer    (write+bash tools)
    ├── qa_compliance  (parallel)
    ├── qa_security    (parallel)
    ├── qa_testing     (parallel)
    └── fixer          (conditional; Phase 5)
    │
    ▼
commit_and_open_pr tool → draft PR on zilly-backend
```

### Ownership boundaries

| Open-SWE owns | Tellus owns |
|---|---|
| Webhook routing (`agent/webapp.py`) | All SOULs (`agent/tellus/souls/`) |
| Sandbox lifecycle + GitHub proxy | Subagent registry (`agent/tellus/subagents.py`) |
| `task` tool + subagent context isolation | Squad-lead orchestration prompt |
| Thread state + checkpoint | Skill library + skill injection |
| `commit_and_open_pr`, `open_pr_if_needed` | Model factory (`agent/tellus/models.py`) |
| Message queue middleware | Domain data layer (Phase 6+) |
| Recursion-limit + tool-error middlewares | Learning sidecar (Phase 6+) |

**Rule:** all Tellus additions live under `agent/tellus/`. The only upstream-facing diff is a ~5-line change in `agent/server.py` to plug in `subagents=[...]` and `model=make_model(...)`. Every other file is untouched, keeping upstream merges conflict-free.

## Components

### Repo layout (post-fork)

```
tellus-openswe/
├── agent/                           # inherited from Open-SWE
│   ├── server.py                    # MODIFIED: get_agent() adds subagents=[...]
│   ├── webapp.py                    # inherited
│   ├── middleware/                  # inherited + ours
│   ├── integrations/                # inherited (sandbox providers)
│   ├── tools/                       # inherited
│   ├── utils/                       # inherited
│   └── tellus/                      # NEW — all Tellus additions isolated here
│       ├── __init__.py
│       ├── souls/
│       │   ├── squad_lead.md
│       │   ├── planner.md
│       │   ├── implementer.md
│       │   ├── qa_compliance.md
│       │   ├── qa_security.md
│       │   ├── qa_testing.md
│       │   └── fixer.md
│       ├── subagents.py             # SUBAGENTS list + registry
│       ├── skills/                  # ported from aegis skills/
│       │   ├── fintech_domain_patterns.md
│       │   ├── zilly_rails_conventions.md
│       │   ├── plaid_fintech.md
│       │   ├── security_baseline.md
│       │   ├── plan_writing.md
│       │   ├── coding_pipeline.md
│       │   ├── security_review.md
│       │   ├── tdd.md
│       │   └── verification.md
│       ├── skill_loader.py          # maps subagent role → skill subset
│       ├── models.py                # make_model(role) factory
│       └── middleware/              # Tellus-specific (empty in v1)
├── langgraph.json                   # inherited
├── pyproject.toml                   # add minimax / langchain-openai deps
└── tests/
    └── tellus/                      # isolated Tellus tests
```

### Subagent registry (sketch)

```python
# agent/tellus/subagents.py
from pathlib import Path
from agent.tellus.models import make_model
from agent.tellus.skill_loader import load_skills_for

SOULS_DIR = Path(__file__).parent / "souls"

def _load_soul(name: str) -> str:
    return (SOULS_DIR / f"{name}.md").read_text()

SUBAGENTS = [
    {
        "name": "planner",
        "description": "Root-cause analysis and implementation plan authoring.",
        "system_prompt": _load_soul("planner") + load_skills_for("planner"),
        "tools": ["read_file", "grep", "list_directory"],
        "model": make_model("planner"),
    },
    {
        "name": "implementer",
        "description": "Implements the approved plan; edits files and runs tests.",
        "system_prompt": _load_soul("implementer") + load_skills_for("implementer"),
        "tools": ["read_file", "write_file", "bash", "grep", "list_directory"],
        "model": make_model("implementer"),
    },
    {
        "name": "qa_compliance",
        "description": "Compliance review of the diff.",
        "system_prompt": _load_soul("qa_compliance") + load_skills_for("qa_compliance"),
        "tools": ["read_file", "grep", "bash"],
        "model": make_model("qa"),
    },
    # qa_security, qa_testing, fixer analogous
]
```

### Tool subsets per subagent

| Subagent | Tools |
|---|---|
| squad-lead | `task` (auto), `commit_and_open_pr`, `list_repos`, `get_branch_name`, `linear_post_comment` *(verify tool availability in Phase 0 — if not a registered Open-SWE tool, it becomes a new Tellus tool wrapping the Linear utility)* |
| planner | `read_file`, `grep`, `list_directory` |
| implementer | `read_file`, `write_file`, `bash`, `grep`, `list_directory` |
| qa_compliance / qa_security / qa_testing | `read_file`, `grep`, `bash` |
| fixer | Same as implementer |

### Skill injection

`skill_loader.load_skills_for(role)` returns concatenated skill markdown for the role. Static mapping in v1 (phase-4 target):

| Role | Skills injected |
|---|---|
| planner | plan_writing, coding_pipeline, fintech_domain_patterns, zilly_rails_conventions |
| implementer | coding_pipeline, zilly_rails_conventions, fintech_domain_patterns, plaid_fintech, tdd |
| qa_compliance | fintech_domain_patterns, security_baseline |
| qa_security | security_baseline, security_review |
| qa_testing | tdd, verification |
| fixer | coding_pipeline, tdd, verification |

Dynamic triage-driven selection is a Phase 7+ concern.

### Model factory

```python
# agent/tellus/models.py
from langchain_community.chat_models import MiniMaxChat
import os

def make_model(role: str):
    # Single provider in v1; extend with role-based overrides later.
    return MiniMaxChat(
        model=os.environ.get("MINIMAX_MODEL", "abab6.5-chat"),
        minimax_api_key=os.environ["MINIMAX_API_KEY"],
        temperature=0.2 if role in {"planner", "qa_security", "qa_compliance"} else 0.4,
    )
```

(If MiniMax tool-calling proves unreliable in Phase 0, `make_model` switches to OpenAI-compatible client against MiniMax's endpoint; behavior contract unchanged.)

## Data flow (Phase 4 happy-path)

1. User `@mentions` the Tellus agent on a Linear ticket.
2. Linear webhook → `POST /webhooks/linear` → webapp resolves repo and creates `thread_id = hash(issue_id)`.
3. LangGraph spawns or resumes the thread; sandbox is created or reused from cache; GitHub App token is injected via proxy; `zilly-backend` is cloned and the branch `tellus-swe/<issue-id>` is checked out.
4. Squad-lead deep-agent receives the ticket context. Its SOUL encodes the orchestration rules, team roster, and pipeline stages.
5. Squad-lead invokes `task("planner", prompt=ticket_context)`. The planner runs in its own isolated context, explores the repo, and writes `/workspace/plan.md`. It returns a summary message to the lead.
6. Squad-lead invokes `task("implementer", prompt="implement /workspace/plan.md")`. The implementer reads the plan, edits files, runs tests via `bash`, commits locally.
7. Squad-lead fans out QA trio in parallel: `task("qa_compliance")`, `task("qa_security")`, `task("qa_testing")`. Each returns a structured JSON report.
8. Squad-lead posts an aggregated summary to Linear via `linear_post_comment`.
9. Squad-lead invokes `commit_and_open_pr`, which pushes the branch and opens a draft PR on `zilly-backend`. The PR body includes the plan summary and QA reports.
10. `open_pr_if_needed` middleware runs as a safety net if the lead forgot step 9.
11. Thread terminates; checkpoint is saved; sandbox persists for follow-ups.

### State channels

| Channel | Scope | Backing |
|---|---|---|
| Messages | conversation history | LangGraph checkpoint (Postgres) |
| Sandbox files (plan.md, source, tests) | per-ticket workspace | LangSmith Sandbox disk (keyed by `sandbox_id`) |
| Thread metadata (`sandbox_id`, `github_token_encrypted`, `linear_issue`) | per-ticket | LangGraph thread metadata |
| Nudges (Linear/Slack comments mid-run) | per-thread queue | LangGraph Store → drained by `check_message_queue_before_model` |
| Domain data (RunOutcome, AgentSession — Phase 6+) | cross-ticket | External Postgres/SQLite, not in LangGraph |

### Inter-subagent data passing

- **Primary:** sandbox files (`/workspace/plan.md`, `/workspace/qa-*.json`) read by the next subagent.
- **Secondary:** the `task` tool's return message (text summary) flows back to the lead's context.
- The lead passes a plan *path* to the implementer, not the raw plan content. This keeps the lead's context slim and lets subagents read canonical artifacts from disk.

### Follow-up flow

A user comment on the PR or the Linear ticket routes back to the same `thread_id`, reuses the same sandbox and checkpoint, and is queued as a `HumanMessage` before the next model call via `check_message_queue_before_model`.

## Error handling

### Inherited (no new code)

| Failure | Handled by |
|---|---|
| Sandbox disconnect | `check_or_recreate_sandbox` |
| Tool execution error | `ToolErrorMiddleware` |
| GitHub API flake | `commit_and_open_pr` internal retry |
| Agent skipped PR | `open_pr_if_needed` middleware |
| Empty model response | `ensure_no_empty_msg` middleware |
| Recursion limit | `DEFAULT_RECURSION_LIMIT=1000` |

### New failure modes we introduce

| Failure | Handling |
|---|---|
| MiniMax 5xx / rate-limit | `make_model` wraps the client with `tenacity` retry (exponential backoff, 3 attempts); structured log on exhaustion. |
| MiniMax tool-call malformed | Rely on LangGraph tool retry + `ToolErrorMiddleware`. Chronic failure → env var flip to a Claude fallback per role. |
| Missing SOUL file | Loud fail at boot (`_load_soul` raises `FileNotFoundError`). Never run with an empty system prompt. |
| Missing skill file | Same loud fail, checked at subagent registration. |
| Subagent fails internally | `task` tool returns the error summary to the lead. Lead decides: retry, try differently, or post a Linear failure comment. Agentic recovery. |
| Subagent loops (implementer can't pass tests) | Recursion limit catches. Lead posts failure comment; no PR opened. |
| PR open fails (branch conflict, perms) | `commit_and_open_pr` raises → lead posts Linear error comment → thread ends. No silent failure. |
| Lead hallucinates sequence (e.g. implementer before planner) | Happy-path v1 accepts this risk; a `before_tool_call` guard is a Phase-5+ addition. |
| Whole thread crashes | LangGraph checkpoint survives; `@mention` resumes. |

### Observability

- Structured logs per stage: `ticket_id`, `thread_id`, `subagent`, `tool`, `latency_ms`, `tokens_in`, `tokens_out`.
- LangSmith traces (inherited).
- Linear comment on every stage transition, posted by the squad-lead via prompt (not Python).
- Sentry integration for exceptions (Phase 0).
- **Dead-man switch (Phase 6+):** cron scans threads idle > 30 min with no terminal state and posts to ops channel.

## Testing

### Pyramid

| Layer | Scope | Tooling |
|---|---|---|
| Unit | SOUL loader, skill loader, `make_model`, subagent definitions, any middleware | pytest |
| Integration | `create_deep_agent(...)` boots; `task` invocation; sandbox r/w; MiniMax tool-calling smoke | pytest + LangGraph test harness + recorded sandbox |
| E2E | Fake Linear webhook → full pipeline → real PR on test repo | pytest + real sandbox + test GitHub org |
| Manual | Real Linear ticket on `zilly-backend` | Human observation of LangSmith trace + PR |

### Per-phase acceptance criteria (happy path)

| Phase | Acceptance |
|---|---|
| 0 | Vanilla Open-SWE runs; fake Linear webhook → any PR on test repo; MiniMax tool-call smoke green. |
| 1 | Real ticket → Tellus-branded PR. SOUL visible in logs. No subagents yet. |
| 2 | Planner subagent spawns, writes `/workspace/plan.md`, lead references it. Tool subset enforced (no write_file on planner). |
| 3 | Implementer takes over code edits; planner no longer writes code. |
| 4 | QA trio runs in parallel (overlapping timestamps in trace); structured JSON reports valid. |
| 5 | Injected failing test → fixer patches → QA re-runs → PR turns green without human intervention. |

### Fixtures

- `tests/fixtures/linear_webhook.json` — canned Linear payload.
- `tests/fixtures/test_repo/` — minimal Rails app with a known bug for E2E.
- `tests/fixtures/souls/minimal_*.md` — stripped-down SOULs for unit tests (real SOULs kept out of snapshot tests — they churn).
- Recorded sandbox responses for offline integration tests (VCR-style cassettes if LangSmith Sandbox has no replay mode).

### What we do not test

- Open-SWE inherited behavior (message queue, webapp routing, GitHub proxy) — upstream responsibility.
- LangGraph / deepagents internals.
- MiniMax wire protocol.

### Red flags to halt and debug

- Subagent's full context leaks into lead's messages → context isolation broken.
- Same subagent invoked > 5 times → loop.
- PR opens without `/workspace/plan.md` existing → implementer bypassed planner.
- Tool call on a disallowed tool succeeds → tool-subset enforcement broken.

## Phased rollout

| Phase | Deliverable | Exit criteria | Est |
|---|---|---|---|
| **0** | Fork Open-SWE. Configure env (MiniMax key, Linear webhook, GitHub App, LangSmith Sandbox). Vanilla agent runs. | Fake Linear ticket → draft PR on test repo. MiniMax tool-call smoke green. Upstream remote added. | 0.5d |
| **1** | Squad-lead SOUL replaces default prompt. No subagents. Tellus voice + team roster + stage rules baked into the prompt. | Real ticket → Tellus-branded PR. Log shows SOUL loaded. | 0.5d |
| **2** | Planner subagent added via `subagents=[planner]`. Read-only tools enforced. Planner skills injected. | Ticket → squad-lead invokes planner via `task`; `plan.md` appears in sandbox; lead references it when coding. | 1d |
| **3** | Implementer subagent separated from lead. Lead no longer writes code directly. | Plan produced by planner, code by implementer, PR references both. Tool subsets still enforced. | 1d |
| **4** | QA trio (`qa_compliance`, `qa_security`, `qa_testing`) in parallel. Structured reports in PR body. | Trace shows overlapping timestamps. Structured reports valid JSON. | 1d |
| **5** | Fixer subagent added. No hard gate — lead decides agentically when to call it. | Inject failing test → fixer patches → QA re-runs → PR green, no human intervention. | 1d |
| **---** | **Happy-path v1 ships here (~5d total).** First production ticket on `zilly-backend`. | | |
| **6** | Learning sidecar: LangGraph graph runs post-PR-close, records outcome (merged / reverted / closed) to a Postgres `run_outcomes` table. No SOUL evolution yet. | Row per completed ticket with outcome, diff, trace link. | 2d |
| **7** | Memory retrieval: planner pre-fetches top-K similar past outcomes and injects as context. Embeddings via MiniMax or hosted Qdrant. | Retrieval visible in trace. Blind comparison of planner quality vs Phase 5 on a canned ticket set. | 2d |
| **8** | Ops dashboard: thin Next.js UI listing threads, status, PR links, QA reports, manual replay. | Dashboard shows last 20 runs with live status. | 3d |

### Guardrails across all phases

- Every phase = own branch `phase-N-*`, squash-merged after E2E green.
- Every merge runs `/octo:deliver` adversarial review.
- Upstream `open-swe` tracked via cron (weekly `git fetch upstream && rebase` attempt). Divergence is limited to `agent/server.py` + the new `agent/tellus/` tree.
- Kill switch: `TELLUS_DISABLE_SUBAGENTS=1` → falls back to vanilla Open-SWE behavior.
- Feature flag per subagent: e.g. `TELLUS_ENABLE_QA=0`.

## Open risks

1. **MiniMax tool-call reliability under multi-subagent fan-out.** Deep-agents patterns emerged from Claude. Unknown under MiniMax. Phase 0 smoke test required before committing to Phase 2+. Fallback: role-scoped switch to Claude via `make_model`.
2. **No Anthropic prompt caching with MiniMax.** Full token cost every turn. Long SOULs multiply. If budget becomes a constraint, either trim SOULs or accept Claude + caching for the lead/implementer roles.
3. **Agentic gates drift.** Without Python enforcement, the lead may skip stages or proceed with a bad plan. Acceptable for v1 happy path; revisit with middleware safety nets at Phase 5 close if seen in practice.
4. **Fixer ↔ QA loop without Python control.** The lead must choose to re-invoke QA after fixer. Risk of infinite loops; bounded by `DEFAULT_RECURSION_LIMIT`. Add an explicit attempts counter in middleware if seen in practice.
5. **Upstream rewrite churn.** Open-SWE is young; `main` rewrote itself from the TS monorepo to Python in the recent past. Another rewrite could invalidate parts of this design. Mitigation: isolate all Tellus code under `agent/tellus/` and keep the `server.py` diff minimal.

## Appendix: mapping Aegis → Tellus Open-SWE

| Aegis concept | Tellus Open-SWE equivalent |
|---|---|
| DeerFlow harness | Open-SWE / Deep Agents harness |
| `aegis_pipeline` StateGraph supervisor | Squad-lead deep-agent + prompt-driven stage ordering |
| `planner`, `implementer`, `qa-lead`, etc. SOULs | Subagents registered via `subagents=[...]`, SOULs ported as markdown under `agent/tellus/souls/` |
| `planning_ensemble` 3-draft-merge | Future phase (post-v2); not in scope here |
| Plan-eval gate (score ≥ 8) | Deferred; insertion point = middleware `@after_subagent("planner")` |
| QA composite gate | Deferred; insertion point = middleware `@after_subagent` for QA trio |
| `set_triage` DB tool + Issue/AgentSession/Decision/RunOutcome tables | Phase 6+; external Postgres, out-of-graph |
| `learning_pipeline` graph | Phase 6+; separate LangGraph sidecar |
| `soul-synthesizer` | Phase 6+ (data capture) / Phase 8+ (active rewriting) |
| Ops dashboard | Phase 8 new thin dashboard |
| DeerFlow sandbox + streaming | LangSmith Sandbox + LangGraph native streaming |
| `start_pipeline` tool | N/A — webhook-driven entry |
| HITL approval gates | Removed by design |
