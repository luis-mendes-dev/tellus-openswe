# Phase 0 — Bootstrap & MiniMax Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Boot the forked Open-SWE unchanged on MiniMax as its sole LLM provider, wire all required secrets, and prove end-to-end that a Linear @mention produces a draft PR on a test repository.

**Architecture:** Fork stays on Open-SWE upstream. All Tellus additions land under `agent/tellus/`. Only upstream diff = one import swap in `agent/server.py` so the agent uses `agent.tellus.models.make_model` (which supports a `minimax:` model-id prefix) instead of `agent.utils.model.make_model`. No subagents, no SOUL changes, no pipeline code — those come in Phase 1+.

**Tech Stack:** Python 3.12, LangGraph 1.0+, Deep Agents 0.5+, LangChain OpenAI-compatible client pointed at the MiniMax endpoint, LangSmith Sandbox (default), GitHub App auth, Linear webhooks. Dev loop uses `langgraph dev`.

**Pre-requisites (done out-of-band, not plan tasks):**
- MiniMax API key from https://api.minimax.io/
- GitHub App installation on a dedicated test repo (e.g. `luis-mendes-dev/tellus-openswe-playground`). App must have `contents:write`, `pull-requests:write`, `issues:read`. Note the App ID, private key, and installation ID.
- Linear API token + webhook secret + a test workspace/team reachable from the webhook.
- LangSmith API key + Sandbox access enabled on your LangSmith workspace.

---

## File Structure

**New files (all under `agent/tellus/`):**

| File | Responsibility |
|---|---|
| `agent/tellus/__init__.py` | Package marker. Empty. |
| `agent/tellus/models.py` | `make_model(...)` — supports `minimax:<model>` prefix, falls through to upstream `make_model` for everything else. |
| `agent/tellus/README.md` | One-page note for future maintainers: "everything Tellus-specific lives here; upstream is untouched." |
| `tests/tellus/__init__.py` | Package marker. Empty. |
| `tests/tellus/test_models.py` | Unit tests for `tellus.models.make_model`. |

**Modified files:**

| File | Change |
|---|---|
| `agent/server.py` | One import swap: `from .utils.model import make_model` → `from .tellus.models import make_model`. No other changes. |
| `.env.example` | Add Tellus-required env block (MiniMax + reminder of inherited vars). |
| `README.md` | Add a short "Running as Tellus fork" section at the top. |

**Untouched:** every other file under `agent/`, including `agent/utils/model.py` (upstream wrapper remains available for fallback).

---

## Task 1: Create Tellus package scaffolding

**Files:**
- Create: `agent/tellus/__init__.py`
- Create: `agent/tellus/README.md`
- Create: `tests/tellus/__init__.py`

- [ ] **Step 1: Create the Tellus package marker**

Create `agent/tellus/__init__.py`:

```python
"""Tellus additions on top of Open-SWE.

Everything under this package is Tellus-specific (SOULs, subagents, model
factories, skill loaders, middleware). Upstream Open-SWE files remain
unchanged; the only exception is a single import swap in `agent/server.py`.
"""
```

- [ ] **Step 2: Create the README placeholder**

Create `agent/tellus/README.md`:

```markdown
# agent/tellus/

Tellus additions on top of Open-SWE. Everything Tellus-specific lives here so
upstream merges from `langchain-ai/open-swe` stay conflict-free.

## Layout (grows as phases ship)

- `models.py` — model factory (supports `minimax:` prefix)
- `souls/` — specialist system prompts (Phase 1+)
- `skills/` — domain knowledge injected into subagent prompts (Phase 2+)
- `skill_loader.py` — maps subagent role → skills (Phase 2+)
- `subagents.py` — registered subagents (Phase 2+)
- `middleware/` — Tellus-specific middleware (Phase 6+)

## Upstream diff rule

The only file outside `agent/tellus/` we modify is `agent/server.py`, and only
to swap a single import. Any new upstream diff needs an entry here with a
justification before it lands.
```

- [ ] **Step 3: Create the test package marker**

Create `tests/tellus/__init__.py`:

```python
```

- [ ] **Step 4: Commit**

```bash
git add agent/tellus/__init__.py agent/tellus/README.md tests/tellus/__init__.py
git commit -m "feat(tellus): add package scaffolding for Tellus additions"
```

---

## Task 2: Add the MiniMax-aware model factory

**Files:**
- Create: `agent/tellus/models.py`
- Test: `tests/tellus/test_models.py`

**Context:** Upstream `agent/utils/model.py` is a thin wrapper around LangChain's `init_chat_model`. It has one special case: if the model id starts with `openai:`, it injects the Responses WebSocket base URL. MiniMax exposes an OpenAI-compatible endpoint at `https://api.minimax.io/v1`, so we can reuse the OpenAI client class but must point it at MiniMax and bypass the Responses-API flag. We add a new `minimax:` prefix that resolves to the OpenAI provider underneath but with a MiniMax `base_url` and `api_key`. Everything else delegates to the upstream factory.

- [ ] **Step 1: Write the failing test — minimax prefix resolves via OpenAI provider**

Create `tests/tellus/test_models.py`:

```python
"""Unit tests for agent.tellus.models."""
from __future__ import annotations

import os
from unittest import mock

import pytest

from agent.tellus import models as tellus_models


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Isolate every test from host env."""
    for key in (
        "MINIMAX_API_KEY",
        "MINIMAX_BASE_URL",
        "OPENAI_API_KEY",
        "LLM_MODEL_ID",
    ):
        monkeypatch.delenv(key, raising=False)
    yield


def test_minimax_prefix_routes_to_openai_provider_with_minimax_base_url(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    captured: dict = {}

    def fake_init_chat_model(model, **kwargs):
        captured["model"] = model
        captured["kwargs"] = kwargs
        return mock.sentinel.chat_model

    monkeypatch.setattr(tellus_models, "init_chat_model", fake_init_chat_model)

    result = tellus_models.make_model("minimax:MiniMax-M1", max_tokens=1234)

    assert result is mock.sentinel.chat_model
    assert captured["model"] == "openai:MiniMax-M1"
    assert captured["kwargs"]["base_url"] == "https://api.minimax.io/v1"
    assert captured["kwargs"]["api_key"] == "test-key"
    assert captured["kwargs"]["max_tokens"] == 1234
    # minimax OpenAI-compatible endpoint is chat-completions, not Responses API
    assert "use_responses_api" not in captured["kwargs"]


def test_minimax_prefix_requires_api_key(monkeypatch):
    with pytest.raises(KeyError):
        tellus_models.make_model("minimax:MiniMax-M1")


def test_minimax_base_url_env_override(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    monkeypatch.setenv("MINIMAX_BASE_URL", "https://minimax.internal/v1")

    captured: dict = {}

    def fake_init_chat_model(model, **kwargs):
        captured["kwargs"] = kwargs
        return mock.sentinel.chat_model

    monkeypatch.setattr(tellus_models, "init_chat_model", fake_init_chat_model)

    tellus_models.make_model("minimax:MiniMax-M1")

    assert captured["kwargs"]["base_url"] == "https://minimax.internal/v1"


def test_non_minimax_prefix_falls_through_to_upstream(monkeypatch):
    """Anthropic and plain openai prefixes must delegate to upstream make_model."""
    called_with: dict = {}

    def fake_upstream(model_id, **kwargs):
        called_with["model_id"] = model_id
        called_with["kwargs"] = kwargs
        return mock.sentinel.upstream_model

    monkeypatch.setattr(tellus_models, "_upstream_make_model", fake_upstream)

    result = tellus_models.make_model("anthropic:claude-opus-4-6", max_tokens=500)

    assert result is mock.sentinel.upstream_model
    assert called_with["model_id"] == "anthropic:claude-opus-4-6"
    assert called_with["kwargs"] == {"max_tokens": 500}


def test_defaults_to_llm_model_id_env(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL_ID", "minimax:MiniMax-M1")

    captured: dict = {}

    def fake_init_chat_model(model, **kwargs):
        captured["model"] = model
        return mock.sentinel.chat_model

    monkeypatch.setattr(tellus_models, "init_chat_model", fake_init_chat_model)

    tellus_models.make_model()  # no model_id arg

    assert captured["model"] == "openai:MiniMax-M1"
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `uv run pytest tests/tellus/test_models.py -v`
Expected: all five tests FAIL with `ModuleNotFoundError: No module named 'agent.tellus.models'`.

- [ ] **Step 3: Implement `agent/tellus/models.py`**

Create `agent/tellus/models.py`:

```python
"""Tellus model factory.

Adds a `minimax:<model>` prefix that resolves to LangChain's OpenAI provider
pointed at MiniMax's OpenAI-compatible endpoint. All other prefixes
(`anthropic:`, `openai:`, `google_genai:`, ...) fall through to upstream
`agent.utils.model.make_model` unchanged.

Env vars read:
    MINIMAX_API_KEY   — required for `minimax:` prefix
    MINIMAX_BASE_URL  — optional override; default https://api.minimax.io/v1
    LLM_MODEL_ID      — default model id when none is passed
"""
from __future__ import annotations

import os

from langchain.chat_models import init_chat_model

from agent.utils.model import make_model as _upstream_make_model

MINIMAX_DEFAULT_BASE_URL = "https://api.minimax.io/v1"
DEFAULT_LLM_MODEL_ID = "minimax:MiniMax-M1"


def make_model(model_id: str | None = None, **kwargs):
    """Create a chat model. Supports a `minimax:` prefix on top of upstream."""
    effective_id = model_id or os.environ.get("LLM_MODEL_ID", DEFAULT_LLM_MODEL_ID)

    if effective_id.startswith("minimax:"):
        model_name = effective_id.split(":", 1)[1]
        model_kwargs = dict(kwargs)
        model_kwargs["base_url"] = os.environ.get(
            "MINIMAX_BASE_URL", MINIMAX_DEFAULT_BASE_URL
        )
        model_kwargs["api_key"] = os.environ["MINIMAX_API_KEY"]
        return init_chat_model(model=f"openai:{model_name}", **model_kwargs)

    return _upstream_make_model(effective_id, **kwargs)
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `uv run pytest tests/tellus/test_models.py -v`
Expected: all five tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/tellus/models.py tests/tellus/test_models.py
git commit -m "feat(tellus): MiniMax-aware make_model factory with minimax: prefix"
```

---

## Task 3: Swap the import in `agent/server.py`

**Files:**
- Modify: `agent/server.py:62`

**Context:** `agent/server.py` currently imports `make_model` from `agent.utils.model`. One-line swap to `agent.tellus.models`. Everything else stays. This is the only upstream file the Phase 0 plan touches.

- [ ] **Step 1: Read the current import line**

Run: `grep -n "from .utils.model" agent/server.py`
Expected: `62:from .utils.model import make_model`

- [ ] **Step 2: Replace the import**

Change line 62 of `agent/server.py`:

```python
# before
from .utils.model import make_model
# after
from .tellus.models import make_model
```

- [ ] **Step 3: Confirm nothing else in `server.py` references `.utils.model`**

Run: `grep -n "utils.model" agent/server.py`
Expected: no output (empty match).

- [ ] **Step 4: Confirm `make_model` is still called with the same signature**

Run: `grep -n "make_model(" agent/server.py`
Expected: one line — `make_model(os.environ.get("LLM_MODEL_ID", DEFAULT_LLM_MODEL_ID), max_tokens=20_000,` — unchanged.

- [ ] **Step 5: Run the Tellus tests to confirm the swap did not regress us**

Run: `uv run pytest tests/tellus/ -v`
Expected: all five tests from Task 2 PASS.

- [ ] **Step 6: Optional wider sweep**

Run: `uv run pytest tests/ -v 2>&1 | tail -40`
Expected: upstream tests either PASS or SKIP (some require env creds). If a test FAILS because it patched `agent.utils.model.make_model` directly, that is upstream-owned — do NOT edit upstream tests. Note the failure in the commit message and move on; upstream will self-correct once its test understands the convention.

- [ ] **Step 7: Commit**

```bash
git add agent/server.py
git commit -m "chore(tellus): point server.py at tellus.models.make_model"
```

---

## Task 4: Document Tellus env vars in `.env.example`

**Files:**
- Modify: `.env.example` (create if missing)

**Context:** `langgraph.json` loads `.env`. We need a documented `.env.example` that lists everything a fresh clone needs. Open-SWE already has this; we only append a Tellus block. If `.env.example` does not exist, create it fresh with the full var list.

- [ ] **Step 1: Check whether `.env.example` already exists**

Run: `ls -la .env.example 2>&1 || echo MISSING`
Expected output dictates the next step.

- [ ] **Step 2a: If `.env.example` exists, append the Tellus block**

Run: `cat >> .env.example <<'EOF'

# -- Tellus fork --
# Default model id; any prefix supported by agent.tellus.models.make_model
LLM_MODEL_ID=minimax:MiniMax-M1

# Required when LLM_MODEL_ID uses the minimax: prefix
MINIMAX_API_KEY=
# Optional: override MiniMax base URL (defaults to https://api.minimax.io/v1)
# MINIMAX_BASE_URL=https://api.minimax.io/v1

# Feature flags (Phase 2+)
# TELLUS_DISABLE_SUBAGENTS=0
EOF`

- [ ] **Step 2b: If `.env.example` is missing, create it with the full var list**

Create `.env.example`:

```bash
# LangSmith (required for default sandbox + tracing)
LANGSMITH_API_KEY=
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=tellus-openswe

# Sandbox backend: langsmith | daytona | modal | runloop | local
SANDBOX_TYPE=langsmith

# GitHub App (Open-SWE uses installation tokens, not PATs)
GITHUB_APP_ID=
GITHUB_APP_PRIVATE_KEY=
GITHUB_APP_WEBHOOK_SECRET=

# Linear
LINEAR_API_TOKEN=
LINEAR_WEBHOOK_SECRET=

# Slack (optional; only needed if Slack trigger is used)
SLACK_BOT_TOKEN=
SLACK_SIGNING_SECRET=

# -- Tellus fork --
# Default model id; any prefix supported by agent.tellus.models.make_model
LLM_MODEL_ID=minimax:MiniMax-M1

# Required when LLM_MODEL_ID uses the minimax: prefix
MINIMAX_API_KEY=
# Optional: override MiniMax base URL (defaults to https://api.minimax.io/v1)
# MINIMAX_BASE_URL=https://api.minimax.io/v1

# Feature flags (Phase 2+)
# TELLUS_DISABLE_SUBAGENTS=0
```

- [ ] **Step 3: Sanity-check the final file**

Run: `grep -c "MINIMAX_API_KEY" .env.example`
Expected: `1`

- [ ] **Step 4: Commit**

```bash
git add .env.example
git commit -m "docs(tellus): document Tellus env block in .env.example"
```

---

## Task 5: Copy `.env.example` to `.env` and fill in real credentials

**Files:**
- Create (local only, never committed): `.env`

**Context:** `.env` is `.gitignore`'d. This task is local configuration, not code. The steps ensure the engineer knows which vars are required before `langgraph dev` will start.

- [ ] **Step 1: Copy the template**

Run: `cp .env.example .env`

- [ ] **Step 2: Confirm `.gitignore` still excludes `.env`**

Run: `grep -n "^\.env$" .gitignore`
Expected: a line matching `.env` (not `.env.example`). If not found, ADD `.env` to `.gitignore` before proceeding and commit only the `.gitignore` change.

- [ ] **Step 3: Populate secrets**

Open `.env` and fill in every non-commented value. At minimum for Phase 0 the following must be non-empty:
- `LANGSMITH_API_KEY`
- `GITHUB_APP_ID`
- `GITHUB_APP_PRIVATE_KEY` (paste as a quoted one-line string, `\n`-escaped)
- `GITHUB_APP_WEBHOOK_SECRET`
- `LINEAR_API_TOKEN`
- `LINEAR_WEBHOOK_SECRET`
- `MINIMAX_API_KEY`

- [ ] **Step 4: Verify the file was not accidentally staged**

Run: `git status --short .env`
Expected: no output. If output shows `.env`, run `git restore --staged .env` and fix `.gitignore`.

- [ ] **Step 5: No commit** — local-only file.

---

## Task 6: MiniMax live smoke test (tool-call round-trip)

**Files:**
- Test: `tests/tellus/test_minimax_smoke.py`

**Context:** Unit tests in Task 2 mocked `init_chat_model`. We also need one live test that confirms MiniMax's OpenAI-compatible endpoint actually responds and supports tool calls the way LangChain expects. Marked `@pytest.mark.live` so CI can skip it; it runs only when MiniMax creds are present.

- [ ] **Step 1: Write the smoke test**

Create `tests/tellus/test_minimax_smoke.py`:

```python
"""Live smoke test against MiniMax's OpenAI-compatible endpoint.

Skipped automatically unless MINIMAX_API_KEY is set. Exists to catch
provider-side drift (endpoint URL changes, tool-calling regressions) that
unit tests cannot.
"""
from __future__ import annotations

import os

import pytest
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from agent.tellus.models import make_model

LIVE = os.environ.get("MINIMAX_API_KEY") is not None

pytestmark = pytest.mark.skipif(not LIVE, reason="MINIMAX_API_KEY not set")


@tool
def add(a: int, b: int) -> int:
    """Return a + b."""
    return a + b


def test_minimax_tool_call_round_trip():
    model = make_model("minimax:MiniMax-M1", max_tokens=200).bind_tools([add])

    response = model.invoke(
        [HumanMessage(content="Use the add tool to compute 21 + 21.")]
    )

    tool_calls = getattr(response, "tool_calls", None) or []
    assert tool_calls, f"Expected at least one tool call, got response={response!r}"
    assert tool_calls[0]["name"] == "add"
    args = tool_calls[0]["args"]
    assert int(args.get("a", 0)) == 21
    assert int(args.get("b", 0)) == 21
```

- [ ] **Step 2: Run the smoke test with a real key**

Run: `MINIMAX_API_KEY=$(grep ^MINIMAX_API_KEY= .env | cut -d= -f2-) uv run pytest tests/tellus/test_minimax_smoke.py -v`
Expected: PASS. If MiniMax returns text instead of a tool call, the chosen model ID does not support function calling — switch `LLM_MODEL_ID` to a MiniMax model that does (e.g. `MiniMax-Text-01`) and re-run. Document the final working model ID in a follow-up commit to `.env.example`'s comment.

- [ ] **Step 3: Run without a key to confirm skip behavior**

Run: `env -u MINIMAX_API_KEY uv run pytest tests/tellus/test_minimax_smoke.py -v`
Expected: `SKIPPED` (not FAILED).

- [ ] **Step 4: Commit**

```bash
git add tests/tellus/test_minimax_smoke.py
git commit -m "test(tellus): live MiniMax tool-call smoke test (skipped without key)"
```

---

## Task 7: Boot `langgraph dev` and confirm the graph loads

**Files:** none (manual verification)

**Context:** `langgraph dev` starts the LangGraph server defined in `langgraph.json`. It imports the graph factory, validates the FastAPI webapp mount, and prints the dev URLs. A successful boot proves our import swap and env block did not break the agent module.

- [ ] **Step 1: Install dependencies into the local venv**

Run: `uv sync --extra dev`
Expected: resolves without errors.

- [ ] **Step 2: Boot the dev server**

Run: `uv run langgraph dev --allow-blocking`
Expected output contains (order may vary):
- `Loading graph: agent`
- `Loading HTTP app: agent.webapp:app`
- `Ready! Server at http://127.0.0.1:2024`
- No Python traceback.

If the server fails on import, the most likely cause is a missing env var or a typo in the Task 3 swap. Re-read the stack trace line-by-line before changing code.

- [ ] **Step 3: Hit the health endpoint**

In a second terminal:

Run: `curl -sf http://127.0.0.1:2024/health && echo`
Expected: a 2xx response with a JSON body — `{"status":"ok"}` or similar (see `agent/webapp.py` for the exact shape). What matters: non-empty response, no 404.

- [ ] **Step 4: Stop the server**

`Ctrl-C` the `langgraph dev` process.

- [ ] **Step 5: No commit** — verification only.

---

## Task 8: End-to-end smoke via a real Linear ticket

**Files:** none (manual verification; outcome noted in commit message of Task 9)

**Context:** The true Phase 0 exit criterion is "fake Linear ticket → draft PR on test repo." Implemented as a manual run because webhooks need a reachable public URL. The engineer should use `ngrok` or Cloudflare Tunnel for the first pass.

- [ ] **Step 1: Expose the dev server publicly**

Run (separate terminal): `ngrok http 2024`
Expected: a HTTPS forwarding URL. Copy it.

- [ ] **Step 2: Register the ngrok URL as a Linear webhook**

In Linear → Settings → API → Webhooks:
- URL: `<ngrok-url>/webhooks/linear`
- Events: `Issue` (create, comment)
- Secret: paste `LINEAR_WEBHOOK_SECRET` from `.env`

- [ ] **Step 3: Start `langgraph dev` again**

Run: `uv run langgraph dev --allow-blocking`

- [ ] **Step 4: Create a throwaway Linear issue**

Title: `Phase 0 smoke: add a README line to tellus-openswe-playground`
Description: one paragraph asking the agent to append a line to `README.md`.
Comment: `@openswe please handle repo:luis-mendes-dev/tellus-openswe-playground`
(Use whatever handle Open-SWE's webhook handler matches — check `agent/webapp.py` for the exact mention trigger.)

- [ ] **Step 5: Watch the trace**

In LangSmith, navigate to the project matching `LANGSMITH_PROJECT`. A new thread should appear within ~30 seconds.

- [ ] **Step 6: Verify the PR was opened**

Check the playground repo on GitHub. Expected: a draft PR whose branch name matches the issue-derived slug and whose first commit appends a line to `README.md`.

- [ ] **Step 7: Capture the trace URL and PR URL**

Copy both URLs into a scratch note (`docs/superpowers/plans/_phase-0-verification.md`, see Task 9).

- [ ] **Step 8: No commit yet** — Task 9 records the verification.

**Red flags that halt Phase 0:**
- LangGraph server crashes on first webhook: re-read the traceback; most likely missing env var.
- Agent opens no PR: check LangSmith trace for MiniMax tool-call errors. If MiniMax returned text instead of tool calls, Phase 0 is not done — loop back to Task 6 and pick a different MiniMax model.
- PR opens on the wrong repo: `LINEAR_TEAM_REPO_MAP` env (Open-SWE config) is missing or misconfigured — consult `INSTALLATION.md` before proceeding.

---

## Task 9: Record Phase 0 verification artefacts

**Files:**
- Create: `docs/superpowers/plans/_phase-0-verification.md`

**Context:** We want a committed, dated record that Phase 0's exit criterion was met. Future maintainers should be able to see the exact PR and trace without archaeology.

- [ ] **Step 1: Create the verification note**

Create `docs/superpowers/plans/_phase-0-verification.md`:

```markdown
# Phase 0 Verification

**Date:** YYYY-MM-DD
**Engineer:** <name>
**Fork commit:** <git rev-parse HEAD>
**Model used:** minimax:<exact model id that passed Task 6>

## Evidence

- LangSmith trace: <URL>
- Draft PR: <URL>
- Linear issue: <URL>

## Notes

- Unit tests: `uv run pytest tests/tellus/` → all pass.
- Live smoke: `uv run pytest tests/tellus/test_minimax_smoke.py` → passes with MINIMAX_API_KEY set.
- `langgraph dev` boots cleanly with no tracebacks.

## Known follow-ups (tracked in Phase 1+ plans)

- Squad-lead SOUL port (Phase 1).
- Subagent infrastructure (Phase 2).
- Skill loader (Phase 2).
- Gate middleware (post-v1).
```

Fill in the angle-bracketed fields before committing.

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/_phase-0-verification.md
git commit -m "docs(tellus): Phase 0 verification — MiniMax E2E smoke passed"
```

- [ ] **Step 3: Push the phase-0 branch**

```bash
git push origin main
```

(Or push to a dedicated `phase-0-bootstrap` branch and open a self-PR against `main` if that matches Tellus's review preferences. The spec's guardrails call for per-phase branches, but Phase 0 is so small that a direct push to `main` of the fork is acceptable — decide at execution time.)

---

## Definition of done — Phase 0

- [ ] `agent/tellus/` exists with `__init__.py`, `README.md`, `models.py`.
- [ ] `tests/tellus/test_models.py` passes (5/5).
- [ ] `tests/tellus/test_minimax_smoke.py` passes with real MiniMax key.
- [ ] `agent/server.py` imports `make_model` from `agent.tellus.models` (only upstream diff).
- [ ] `.env.example` documents MiniMax vars; `.env` exists locally and is git-ignored.
- [ ] `langgraph dev` boots with zero tracebacks.
- [ ] A draft PR was opened on the playground repo by the agent in response to a Linear @mention.
- [ ] `_phase-0-verification.md` is committed with the real trace + PR URLs.
- [ ] `upstream` remote points to `langchain-ai/open-swe`; `origin` points to the personal fork.

Once every box above is ticked, Phase 1 (squad-lead SOUL port) gets its own plan.
