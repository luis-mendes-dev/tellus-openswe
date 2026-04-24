# agent/tellus/

Tellus additions on top of Open-SWE. Everything Tellus-specific lives here so
upstream merges from `langchain-ai/open-swe` stay conflict-free.

## Layout (grows as phases ship)

- `models.py` - model factory (supports `minimax:` prefix)
- `souls/` - specialist system prompts (Phase 1+)
- `skills/` - domain knowledge injected into subagent prompts (Phase 2+)
- `skill_loader.py` - maps subagent role -> skills (Phase 2+)
- `subagents.py` - registered subagents (Phase 2+)
- `middleware/` - Tellus-specific middleware (Phase 6+)

## Upstream diff rule

The only file outside `agent/tellus/` we modify is `agent/server.py`, and only
to swap a single import. Any new upstream diff needs an entry here with a
justification before it lands.

## Upstream diff log

The only file outside `agent/tellus/` that Tellus modifies is `agent/server.py`.
As of Phase 1 the diff is two lines, both imports:

- `from .tellus.models import make_model` (Phase 0)
- `from .tellus.prompt import construct_system_prompt` (Phase 1)

Each later phase that adds to this list must append an entry with the phase
number and the exact line. More than ~5 lines of upstream diff is a smell and
should prompt a design review before merging.
