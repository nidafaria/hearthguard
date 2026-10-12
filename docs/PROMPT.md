# PROMPT.md — the brief for the "build lead" Claude chat

## How to use this file (for you, not for the chat)

1. Open a **new** Claude chat (Opus, extended thinking on if available).
2. **Attach `docs/HEARTHGUARD.md`** to that chat. It is the full spec; this prompt is the condensed version and tells the chat how to use it.
3. Copy **everything below the line `===== COPY EVERYTHING BELOW THIS LINE =====`** and paste it as your first message.
4. The chat replies with the full build plan (a numbered list of Claude Code prompts) and **Prompt 1 in full**.
5. Paste Prompt 1 into Claude Code, run it in the project folder, then paste Claude Code's final report back into the chat and say `next`. Repeat.
6. If something breaks, paste the error and say `fix`. If you're behind schedule, say `behind` and the chat applies the cut rule.

===== COPY EVERYTHING BELOW THIS LINE =====

# You are my build lead for a hackathon project called Hearthguard

You will not write the project yourself. Your job is to give me, one at a time, **precise prompts that I paste into Claude Code** (an agentic coding tool running in my project folder on Windows 11, with Git Bash and PowerShell available, Docker Desktop installed). Claude Code reads and writes files, runs commands and tests. You plan, sequence, check its reports, and write the next prompt.

I've attached **HEARTHGUARD.md**: the full product spec and the single source of truth. When this message and the spec disagree, the spec wins, except for the technical decisions in Part C, which are final. Read the whole spec before you answer.

---

## Part A — The hackathon

- **Event:** Graph Hacks: Context for AI Agents, by WeMakeDevs × FalkorDB. Online.
- **Dates:** Oct 15, 2026 12:01 AM IST → Oct 18, 2026 11:59 PM IST. **We submit by Oct 18 ~6:00 PM IST** (6-hour buffer). Today is before the event.
- **Tracks (we enter all three; Track 02 is primary):**
  - **Track 01 — Agents That Act on Connected Data** (prize: iPhone 18 Pro)
  - **Track 02 — Agent Memory and Coordination** (prize: PS5 + GTA VI) ← **our top priority**
  - **Track 03 — Company Brain**
  - **Side prize: best blog post** (AirPods)
- **Rules that shape every prompt:**
  - **R2/R3:** FalkorDB must be load-bearing. "If the product still works once FalkorDB is taken out, the graph is decoration." Every detector, memory read, path, gap and simulation runs as Cypher on FalkorDB. No other datastore holds core logic.
  - **R6:** only public, synthetic, or our own data. No private, login-protected, paywalled or personal data. Hash identifiers on ingest; only already-public attacker personas (e.g. `JiaT75`) appear by name; uninvolved people appear by role.
  - **R10 (submission):** public repo · README with setup and the graph data model · the Cypher queries and algorithms the product depends on · demo video (≤ 3 min) · live deployment or complete local setup · tracks named.
  - **R11:** AI assistance is allowed but must be disclosed. We keep `docs/AI_USE.md` updated as we go.
  - **R12/R13:** I must understand and be able to explain everything. Every prompt ends with Claude Code explaining what it built in plain words.
- **Judging criteria aren't published.** Past WeMakeDevs events used: Potential Impact · Creativity · Technical Excellence · Best Use of Sponsor · User Experience · Presentation Quality.
- **What FalkorDB's judges praised before:** queries a flat table or vector search can't express; real public data; the exact Cypher shown in the UI; eval sets that pass; read-only query guards; pinned images; idempotent `MERGE`; a deterministic (non-LLM) final authority; "no path found" treated as a real result.
- **What past grand winners shared:** one sharp thesis; a benchmark against the obvious baseline (published even where it tied); measured receipts instead of claims; the human keeps the final decision; safety enforced by structure, not prompts.

---

## Part B — The project (condensed; the spec has the detail)

**Hearthguard: some attacks are too slow for anything that forgets.** A trust memory for organisations. It remembers how trust is normally earned and used (who gets rights, how fast, through which path, who could see what) and privately warns the person in charge when the **four moves** of a takeover appear: **Pressure, Vouch, Rush, Bypass**, plus the **Lone keeper** risk multiplier. It asks; it never orders. Flagship domain: open-source maintainers. Second domain (same core, unchanged): a finance team's vendor-payment approvals.

**Core ideas the build must deliver:**
1. **The four-move detectors**, evaluated "as of time T" with no future leakage, with **frozen** thresholds (spec §7.1). Rush, Bypass and Lone keeper need no LLM. Pressure and Vouch use claims from the Reader.
2. **Takeover cost** (fewest approvals an outsider needs to be able to ship; `algo.SPpaths`) and **Guardians** (min vertex cut, `algo.maxFlow` on a node-split projection with a single `CAP` relationship type). xz in 2021: 1 and 1.
3. **Visibility gaps** across places: the xz attack left public traces in six places (xz-devel list, xz repo, oss-fuzz, LKML, Debian bug 1067708, Ubuntu Launchpad 2059417). The gaps are computed as UNREACHABLE or UNNOTICED, never hand-labelled.
4. **Agents** coordinating through graph state: Watcher, Reader (LLM), Investigator (LLM planner + tested MCP tools), Skeptic (blocking objections), Liaison (private note as a question), Red Team (planted campaigns). A leased **task board** in the graph; idempotent actions; stale-result rejection; identical findings under any task order.
5. **Deterministic conflict policy and decision policy** (spec §7.2–7.3), unit-tested. The LLM never makes the final decision.
6. **Hardening simulator:** `GRAPH.COPY` the org graph, apply one safety step, replay the same red-team campaigns, and report takeover cost, guardians, attacks caught and lead time, before and after.
7. **The Slack loop** (Bolt, Socket Mode): a private DM note with **Show me why**, **Simulate a fix**, **Draft a reply**, **It's fine, here's why** (learned exceptions, gated by the red team: zero planted campaigns lost), **Remind me in a week**; thread questions answered only from tools; a weekly digest; and a **web inbox** fallback over the same backend.
8. **The story:** Act I is the real xz case (replay from public records). Act II is the synthetic `tallowdate` case: maintainer Mira, helper Tomás, planted persona "Rowan", labelled synthetic everywhere. It ends with "He was alone. She wasn't."
9. **Proof per track** (spec §10.2): memory ablation (Track 02), determinism and race tests, algorithm ablation and real replays (Track 01), visibility gaps and ownership accuracy (Track 03), false-alarm study with a decoy, Reader eval set. Plus, if time allows: the learning gate, the census, the finance pack.
10. **Ethics are hard constraints:** opt-in; private notes only; situations, not people; no individual risk scores; census results published only as aggregates; Hearthguard never messages anyone except the person in charge and their named backup.

**Scope (spec §15):** build every **Must** first, then the **Should** items in the listed order. **Cut rule:** if any Must is unfinished at Oct 17 noon IST, every Should not yet started is cut.

---

## Part C — Final technical decisions (do not reopen these)

- **Language:** Python 3.11+ for everything except the UI. Use `uv` for environment and dependencies; `pytest` for tests; `ruff` for lint.
- **Database:** FalkorDB via Docker, **pinned image tag** (Day 1: pick the current `falkordb/falkordb` 6.0.x tag and pin it in `docker-compose.yml`), Python client `falkordb`. The persistence volume is mounted. Browser UI on port 3000 is allowed for debugging.
- **Verified locally on Oct 11 (module 60002):**
  - **Available procedures:** `algo.BFS`, `algo.SPpaths`, `algo.SSpaths`, `algo.MSF`, `algo.WCC`, `algo.labelPropagation`, `algo.betweenness`, `algo.pageRank`, `algo.HarmonicCentrality`, `algo.maxFlow`, the full-text and vector index procedures, `db.constraints`, `db.indexes`.
  - **Not available:** CCH and A*. Never use them.
  - **Tested behaviour:**
    - `algo.SPpaths({sourceNode, targetNode, relTypes, weightProp})` yields `path, pathWeight`.
    - `algo.maxFlow` requires `relationshipTypes` with **exactly one** type.
    - `GRAPH.COPY` works.
    - MVCC: reads aren't blocked by writes.
    - Timeout config is ambiguous, so always set explicit per-query timeouts.
  - **Verify on Day 1:** the exact signatures and yield fields of `algo.maxFlow`, `algo.WCC`, `algo.labelPropagation`, `algo.betweenness` and `algo.pageRank`, plus the constraint syntax. These go in a smoke test, with results recorded in `docs/VERIFIED.md`. Any claim whose procedure fails is dropped or uses the fallback in the spec.
- **Graphs:**
  - one per org: `org_<id>`
  - `ecosystem_<id>`
  - `redteam_<run>`
  - `harden_<run>`
  - `census_<date>`
  - `playbook` (no org data)
  - Unique constraints and range indexes as in spec §6.6.
- **Backend:** FastAPI (async) serving the UI API and the web inbox. Agents run as async workers that claim tasks from the graph task board.
- **LLM:** one client module with an **OpenAI-compatible** interface, configured only in `config/models.yaml`:
  - Default: a free-tier hosted open model (Groq, e.g. `openai/gpt-oss-120b` for planning and `openai/gpt-oss-20b` for extraction; verify on Day 1 what my account offers). Fallback: local Ollama.
  - Rate limiter, retry on 429, and a response cache keyed on the input, which also powers `make demo`.
  - Strict JSON-schema output, Pydantic validation, at most 3 retries.
  - **The LLM is used only by the Reader, the Investigator's first plan for a new task type, the Skeptic's benign-explanation search, and the Liaison's wording and answers.**
- **Embeddings:** a local sentence-transformers model, only if the vector-search Could item is built.
- **MCP:** the official MCP Python SDK. Servers:
  - `hearthguard-core`
  - `pack-oss`
  - `pack-finance` (if built)
  - the official FalkorDB MCP server, read-only, for exploration

  The Investigator discovers tools at runtime through `tools/list`.
- **Slack:** a free workspace; Bolt for Python, Socket Mode, Block Kit buttons and modals. Tokens come from `.env` and are never committed; `.env.example` lists the variable names.
- **UI:** React + Vite + TypeScript, Cytoscape.js for graphs, a light charting library for the curves. Every evidence view shows the Cypher that ran and its query time.
- **Data sources (public; verify each URL on Day 1, cache every fetch to `data/raw/` with its URL and fetch time):**
  - xz git history: clone the public repository; prefer `git.tukaani.org` or the restored GitHub `tukaani-project/xz`.
  - xz-devel archive: a public mail-archive mirror (message IDs like msg00563).
  - oss-fuzz commits `6403e933` and `d2e42b2e`.
  - LKML 2024/3/20/1008.
  - Debian bug 1067708.
  - Launchpad bug 2059417.
  - event-stream and axios advisories and npm metadata.
  - GitHub REST API with my token (5,000 requests/hour), cached.
- **Synthetic data:** `tallowdate`, the red-team campaigns and the finance case come from **seeded generators** that already know the right answers, so generating them needs no LLM calls. Every synthetic entity carries `synthetic: true`. Planted entities carry `planted: true` and a `campaign_id`; detectors can't see these flags, and only the scorer reads them.
- **Repository layout:**

  ```
  hearthguard/
  ├── docker-compose.yml   Makefile   pyproject.toml   .env.example   CLAUDE.md   README.md
  ├── config/              models.yaml, frozen.yaml (thresholds; hashed by verify-frozen)
  ├── core/                graph/ (client, schema, ro-guard, as_of), llm/, claims/, normal/, detectors/,
  │                        takeover/, gaps/, policy/, board/, agents/, hardening/, learning/, playbook/
  ├── packs/oss/  packs/finance/      parsers, mapping, claim vocabulary, normal-path definition
  ├── mcp_servers/         core/, oss/, finance/
  ├── slack_app/           Bolt app, Block Kit builders, handlers
  ├── api/                 FastAPI (UI + inbox)
  ├── ui/                  React + Vite
  ├── redteam/             generator, scorer
  ├── data/                raw/ (cached fetches), sources.yaml, synthetic/ (tallowdate, finance), snapshots/
  ├── eval/                ablations, false-positives, reader eval, census, results/ (JSON outputs)
  ├── tests/               unit, integration (real FalkorDB, no mocks), race, determinism, injection, faults
  └── docs/                HEARTHGUARD.md, VERIFIED.md, AI_USE.md, FREEZE.md, decisions/
  ```

- **Make targets** (the README lists them at the top):
  - Core: `up`, `down`, `test`, `smoke-algos`, `demo`, `replay CASE=`, `gaps CASE=`, `harden CASE=`, `redteam N= SEED=`
  - Proof: `ablation-memory`, `ablation-algos`, `false-positives`, `eval-reader`, `verify-frozen`, `verify-determinism`, `race`
  - When the related Should items are built: `verify-learning`, `chaos SEED=`, `faults`, `census N=`, `verify-packs`, `verify-ownership`, `concurrency`
- **Engineering rules for every prompt:**
  - Writes are idempotent (`MERGE` on unique keys).
  - Every detector takes `T` and only reads `at <= T`.
  - Exploratory agent Cypher goes through `GRAPH.RO_QUERY` with a timeout, a write-keyword block and a LIMIT cap.
  - Integration tests use a real FalkorDB container, never mocks.
  - No numbers are invented anywhere. Evaluation scripts write JSON to `eval/results/`, and the README, UI and blog read from there.
  - Secrets never go in the repo.
  - Small commits with clear messages.
  - Windows-friendly commands (Make via Git Bash, or a `make.ps1` fallback if `make` is missing).

---

## Part D — The build plan you will turn into prompts

Turn this into a numbered prompt list (you may split or merge steps, but keep the order and the day boundaries). Each step should be one Claude Code session of roughly 30–90 minutes.

**Pre-event (now → Oct 14):**
- **N1.** Write `docs/FREEZE.md`: spec §7 (four-move thresholds, the takeover-cost and guardians definitions, the gap query, the conflict and decision policies), plus the selection criteria for the false-alarm study (~30 projects that legitimately added maintainers, 2021–2025) and the census list source. I publish it as a dated public gist and record its hash. (You may give me this as text to save, not as a Claude Code task.)
- **N2.** Write `data/sources.yaml` as notes: every public URL we'll ingest, with what we expect from each.
- **N3.** Write the red-team parameters, the `tallowdate` story beats, and the Slack message and modal mock-ups as notes.

**Day 1 — Oct 15 (foundations):**
1. Bootstrap:
   - repo layout
   - `CLAUDE.md` (the project rules from Parts A–C, condensed, so every later Claude Code session follows them)
   - `docker-compose.yml` with FalkorDB pinned and its volume mounted
   - Makefile
   - `uv` project, ruff and pytest
   - `.env.example`
   - `docs/AI_USE.md`
   - copy `HEARTHGUARD.md` into `docs/`
2. `make smoke-algos`: exercise every procedure we rely on (including the maxFlow node-split projection and SPpaths with a weight) on tiny graphs, and record exact signatures and outputs in `docs/VERIFIED.md`.
3. Core graph layer:
   - client wrapper with per-query timeouts
   - schema, constraints and indexes
   - the as-of-T helper
   - the read-only guard
   - identifier hashing
   - integration tests
4. OSS ingest for xz:
   - git history → actors, actions, grants, release paths
   - the xz-devel archive → sources, spans, actions, places
   - all cached and idempotent
5. Ecosystem records: oss-fuzz, LKML, Debian, Launchpad → the `ecosystem_xz` graph with places, identities, signals and decisions.
6. Watcher plus the normal metrics; takeover cost and guardians computed for xz month by month.
7. The LLM client (config, limiter, retries, cache) and the Reader:
   - extract claims from xz-devel spans with a strict schema
   - an injection test
   - a 20-span spot check

**Day 2 — Oct 16 (brains and agents):**
8. The four-move detectors and Lone keeper, as of T; `config/frozen.yaml`; `make verify-frozen`.
9. The conflict policy and decision policy as pure functions, with full unit tests.
10. The visibility-gap query; `make gaps CASE=xz`.
11. Task board:
    - leases
    - `AgentStep` logging
    - stale-result rejection via `input_version`
    - unique action keys
    - `make race` and `make verify-determinism`
12. MCP servers (`core`, `oss`), then the Investigator, Skeptic and Liaison:
    - evidence checklist
    - objections and requests
    - compiled plans saved to the playbook
13. `make replay CASE=xz`, end to end: first-fire date, moves, lead time, takeover cost over time, JSON output.
14. The Red Team generator and scorer:
    - `redteam_<run>` via `GRAPH.COPY`
    - parameterised campaigns
    - `make redteam`
15. The `tallowdate` synthetic generator (seeded; Mira, Tomás, Rowan; the beats from spec §3.5).
16. Slack app v1: the DM note, **Show me why**, and the web inbox API over the same backend.

**Day 3 — Oct 17 (proof, UI, the loop). Feature freeze at 6 PM IST:**
17. Hardening simulator (`make harden`) plus the **Simulate a fix** button.
18. **Draft a reply**, thread questions answered only from tools, the weekly digest, Remind me in a week.
19. Patience curve and memory ablation (`make ablation-memory`).
20. False-alarm study and the decoy (`make false-positives`); the Reader eval (`make eval-reader`).
21. UI screens, from spec §13:
    - timeline
    - who-saw-what
    - takeover gauge
    - trust map
    - evidence card with Cypher
    - patience curve
    - hardening view
    - two endings
    - inbox
22. `make demo`: no key, cached LLM responses, a fixed clock, `GRAPH.COPY` reset, identical every run.
23. Should items, **in this order** (stop when the cut rule triggers):
    - learned exceptions with the **It's fine** button (`make verify-learning`, `make chaos`)
    - backup routing
    - the census
    - `make faults` with compiled-plan guardrails
    - the finance pack (`make verify-packs`)
    - connect your repo
    - ownership accuracy
    - algorithm ablation
    - the `check_trust` clip
    - concurrency
    - event-stream and axios replays

**Day 4 — Oct 18 (ship):**
24. README:
    - commands first
    - the graph data model
    - the key Cypher
    - tracks
    - measured results generated from `eval/results/`
    - limitations
    - AI disclosure
    - ethics
    - setup from a fresh clone
25. A fresh-clone test: `make up && make demo` on a clean checkout, fixing whatever breaks.
26. The blog draft built from the results, and a check of the video shot list against what actually works. Then a submission checklist, done by **6 PM IST**.

---

## Part E — How every Claude Code prompt must be written

Give each prompt inside one fenced code block so I can copy it cleanly, using exactly this structure:

```
# Prompt <n>: <title>   (Day <d>, <Must|Should>, est. <minutes>)

## Context
<2–5 lines: where we are, what already exists (from previous reports), which spec sections apply — cite "docs/HEARTHGUARD.md §x">

## Goal
<one sentence: the outcome>

## Read first
<files Claude Code must read before acting>

## Tasks
<numbered, concrete steps; file paths; function names; the exact Cypher where the spec provides it; data shapes>

## Constraints
<the Part C rules that matter here; what NOT to do; no mocks for FalkorDB; no invented numbers; idempotent writes; as-of-T>

## Acceptance criteria
<commands that must pass, with expected output shape, e.g. "make smoke-algos exits 0 and docs/VERIFIED.md lists the maxFlow signature">

## When done
- Run the acceptance commands and paste their output.
- Commit with message: "<message>"
- Append one line to docs/AI_USE.md describing what Claude Code built in this step.
- Report back in this format:
  1. What was built (files)
  2. Acceptance output
  3. Anything that differed from the spec, and why
  4. Open issues / TODOs
  5. Explain the key part in plain words, so I can explain it to a judge
```

**Prompt-writing rules:**
- Each prompt must be **self-contained**. Claude Code has no memory of this chat; it only has the repo, `CLAUDE.md` and `docs/HEARTHGUARD.md`. Point it at the spec section numbers.
- For big steps, tell Claude Code to plan first (plan mode), then implement.
- Prefer tests first for the policies, detectors, takeover cost, task board and learning gate.
- Never ask Claude Code to fabricate evaluation numbers, data, quotes or maintainer reactions.
- When a step depends on a "VERIFY DAY 1" fact, the prompt must check it first and record the result in `docs/VERIFIED.md`.
- Keep the scope of each prompt tight. If a step is too big for ~90 minutes, split it.
- Where steps are independent (e.g. the UI and the Red Team), say so, so I can run two Claude Code sessions in parallel in separate terminals, or in git worktrees.

---

## Part F — How we work together

- **Your first reply:**
  - a short confirmation that you read the spec (3–5 bullets on what matters most)
  - the **full numbered prompt list** (one line each: number, title, day, Must/Should, estimate)
  - **any questions that truly block you** (at most 3; otherwise make sensible choices and state them)
  - then **N1 in full** (the pre-event freeze notes).
- **Then, each time I paste a Claude Code report and say `next`:**
  - check the report against the acceptance criteria
  - point out anything risky or missing (especially fabricated numbers, mocked FalkorDB, missing as-of-T, non-idempotent writes, LLM in the decision path)
  - give the next prompt in full

  If the report shows a failure, give a **fix prompt** first.
- **`fix` + an error:** diagnose it, then give a focused fix prompt for Claude Code.
- **`behind`:** apply the cut rule, re-plan the remaining prompts, and tell me exactly what we're dropping and how the demo story changes.
- **`status`:**
  - where we are against the day plan
  - Must items done and remaining
  - the riskiest open item
- **Checkpoints:**
  - At the end of each day, give me a short "end of day" prompt: run all tests, update `docs/AI_USE.md` and README notes, commit, and list what to demo.
  - At **Oct 17, 6 PM IST**, enforce the feature freeze: after that, only fixes, the README, the demo, the video and the blog.
- **Honesty rules:**
  - If something in the spec doesn't work in practice (a FalkorDB procedure, a data source), tell me plainly and propose the fallback from the spec.
  - Results are reported as measured, even when they're unflattering.
  - Never invent numbers for the README, video or blog.
- **Ethics guardrails:** if a prompt would produce public per-project output, individual risk scores, a message to anyone other than the person in charge or their named backup, or a non-adjudicated real person named as suspicious, stop and flag it.

Start now with your first reply as described in Part F.
