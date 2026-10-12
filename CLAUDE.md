# CLAUDE.md: Hearthguard project rules

Read `docs/HEARTHGUARD.md` (the spec) before any non-trivial change. Section numbers below refer to it.

## Stack
- Python 3.11+ for everything except the UI (React + Vite + TypeScript in `ui/`).
- Environment and dependencies: `uv`. Run tools with `uv run`, for example `uv run pytest`.
- Tests: `pytest`. Lint and format: `ruff`.
- Backend: FastAPI (async). Agents are async workers that claim tasks from the graph task board.
- Make targets are in `Makefile`. On Windows without `make`, use `make.ps1`.

## Load-bearing graph (spec §1 R2/R3)
- FalkorDB is load-bearing. Every detector, memory read, trust path, takeover cost, visibility gap, and hardening replay runs on it. No secondary datastore holds core logic.
- Integration tests use a real FalkorDB container. No mocks for the graph.
- Graph names: `org_<id>`, `ecosystem_<id>`, `redteam_<run>`, `harden_<run>`, `census_<date>`, `playbook`.
- Procedures that are NOT available in 6.0: CCH and A*. Never use them.
- `algo.maxFlow` takes exactly one relationship type.
- Always set an explicit per-query timeout. The module config is ambiguous (`TIMEOUT 1000` at load, `TIMEOUT_DEFAULT` = 0).
- Persistence and image: the image is pinned (`falkordb/falkordb:6.0.2`), never `:latest`.

## Writes and reads
- Writes are idempotent: `MERGE` on unique keys (§6.6).
- Every detector takes `T` and reads only at `<= T` (the as-of-T helper).
- Exploratory agent Cypher goes through `GRAPH.RO_QUERY` with an explicit timeout, a write-keyword block, and a `LIMIT` cap.

## The LLM is never in the decision path (§8.4)
- The LLM is used only by the Reader, the Investigator's first plan for a new task type, the Skeptic's benign-explanation search, and the Liaison's wording and answers.
- Detectors, the conflict policy, the decision policy, takeover cost, guardians, gaps, and hardening are deterministic code, unit-tested.
- LLM output is strict JSON schema, validated with Pydantic, at most 3 retries. Its responses are cached.

## Honesty about numbers
- No invented numbers, data, quotes, or maintainer reactions anywhere.
- Evaluation scripts write JSON to `eval/results/`. The README, UI, and blog read from there.
- A "VERIFY DAY 1" fact is checked first, and the result goes in `docs/VERIFIED.md`.

## Data and privacy (§1 R6, §4.5)
- Public, synthetic, or our own data only. Identifiers are hashed on ingest.
- Every synthetic entity carries `synthetic: true`. Planted entities carry `planted: true` and a `campaign_id`. Detectors must never read these flags; only the scorer does.
- No public per-project output.
- Cache every fetch to `data/raw/` with its URL and fetch time. `data/raw/` is git-ignored.

## Secrets
- Secrets never go in the repo. Tokens come from `.env`. `.env.example` lists names only.

## Process
- Small commits with clear messages.
- Every module has a named owner who can explain it (R12/R13). Record design decisions in `docs/decisions/`.
- Log each AI-assisted step as one line in `docs/AI_USE.md`.
- Do not edit `docs/HEARTHGUARD.md`, `docs/FREEZE.md`, or `docs/FREEZE.sha256` unless the user asks for it. Those are frozen (§10.1).
- Each prompt must be self-contained. Claude Code has no memory of earlier chats. Point it at the spec section numbers.
- Prefer tests first for policies, detectors, takeover cost, the task board, and the learning gate.
- Scope tightly. If a step will not fit in about 90 minutes, split it.
