# Hearthguard

> Some attacks are too slow for anything that forgets.

Hearthguard keeps a memory of who could change an open-source project, and how that changed over time. It stores that memory as a graph in FalkorDB (docs/HEARTHGUARD.md §5). Four slow moves (Pressure, Vouch, Rush, Bypass) and one multiplier (Lone keeper) are read from that graph by plain code. An LLM reads text into typed claims; it is never in the decision path (docs/HEARTHGUARD.md §8.4).

It was built to ask one question: would this memory have flagged the xz backdoor, using only public data? In this build, it does **not** detect the xz backdoor, and it does not claim to. What it does do, and what it does not, is listed under "What is measured" and "Limitations".

**Status: provisional. The project is not complete.** The score and every row's status are in eval/results/completion_full.md. The rules are not frozen: docs/FREEZE.md is a draft.

**Deployment: local only.** Nothing is deployed or hosted. Everything runs on your own machine.

**Demo video:** not recorded yet. There is no link.

## Setup

This is the whole local setup. A judge needs no API key for any of it.

1. Install `uv` (https://docs.astral.sh/uv/) and Docker. For the UI, also Node and npm.
2. `uv sync`
3. Create a `.env` in the repo root with `HEARTHGUARD_HASH_SALT=<any long random text>`. It is git-ignored; `.env.example` lists the names. Hashing refuses to run without it.
4. Start the database: `docker compose up -d` (Windows: `powershell -ExecutionPolicy Bypass -File .\make.ps1 up`). The image is pinned to `falkordb/falkordb:6.0.2`. If a port is taken, set `FALKORDB_PORT` or `FALKORDB_UI_PORT` in `.env`.
5. Run the checks below.

The demo needs none of the three (no key, no network, no database); it prints from saved result files:

```powershell
uv run python -m eval.demo
```

On Windows without `make`, every target below runs as `powershell -ExecutionPolicy Bypass -File .\make.ps1 <target>`. A plain `.\make.ps1` fails on a default Windows install ("running scripts is disabled"), because Windows defaults to the Restricted policy. Judge path with expected outputs: [docs/judge_guide.md](docs/judge_guide.md).

Tests: `uv run pytest` (Windows: `powershell -ExecutionPolicy Bypass -File .\make.ps1 test`). The FalkorDB-backed tests need step 3 and step 4. Tests that need git-ignored data (`data/raw/`) skip with a reason.

## Commands

Each name works as `make <name>`, or on Windows as `powershell -ExecutionPolicy Bypass -File .\make.ps1 <name>`, where `make.ps1` lists it. Positional arguments work (`.\make.ps1 replay xz`). Named ones are passed as parameters: the red team is `.\make.ps1 redteam -N 200 -Seed 7 -Case tallowdate` (N and seed default to 200 and 7). Commands shown in full (`uv run python -m <module>`) are run exactly so.

| Command | What it does | Needs |
|---|---|---|
| `uv run python -m eval.demo` | Print the xz replay table, the visibility gaps, the hardening summary and the tallowdate summary (synthetic, labelled) | files only |
| `up` / `down` | Start or stop FalkorDB | Docker |
| `test` | Run the test suite | uv; FalkorDB and `.env` for the full suite |
| `lint` | ruff check and format check | uv |
| `smoke-algos` | Re-check each FalkorDB procedure the product depends on | FalkorDB |
| `ingest-xz`, `normal-xz`, `takeover-xz`, `detectors-xz`, `pressure-vouch-xz`, `quarterly-xz` | Build `org_xz` from the public xz git history and run the detectors at each quarter-end | FalkorDB; fetches the public xz git history into `data/raw/xz.git` if it is absent (network) |
| `decision-xz` | The decision policy on the saved statuses | files only |
| `replay CASE=xz` | Rewrite `eval/results/xz_replay.json` and `.md` from saved files | files only |
| `ecosystem-xz`, `gaps CASE=xz` | Load `ecosystem_xz` and compute the visibility gaps; print them (roles only) | network, FalkorDB; files only for `gaps` |
| `tallowdate-run` | The synthetic tallowdate history, load to demo script | FalkorDB, `.env` |
| `redteam N=200 SEED=7 CASE=tallowdate` | Plant N campaigns into copies of a case graph and score the frozen detectors | FalkorDB |
| `harden CASE=xz` | Each hardening step on a copy of the case graph, the same campaigns. Slow: about 38 minutes at the default N=200 | FalkorDB |
| `uv run python -m eval.ablation_memory` | Full vs forgetful memory (last 90 / 30 days) on the same campaigns | FalkorDB, tallowdate loaded |
| `uv run python -m eval.ablation_algos` | Vouch components, SPpaths and maxFlow off one at a time | FalkorDB, tallowdate loaded |
| `uv run python -m eval.incidents_fetch` | Cache the public event-stream and axios records (npm registry, OSV, GitHub issues) | network |
| `uv run python -m eval.incidents_load` | Load them into `org_event_stream` and `org_axios`, twice, and check the counts | FalkorDB |
| `uv run python -m eval.replay_event_stream`, `uv run python -m eval.replay_axios` | Replay the two incidents with the frozen detectors | FalkorDB, incidents loaded |
| `uv run python -m eval.verify_packs` | The finance case runs with the OSS pack removed | FalkorDB |
| `queries` (`uv run python -m eval.queries_doc`) | Rewrite `docs/queries.md` from the query constants in the code | files only |
| `ui` | Read-only page at http://localhost:5173 | Node, npm |
| `inbox` | The local inbox at http://127.0.0.1:8765/#/inbox, the same note and thread as Slack | Node, npm |
| `llm-test`, `reader-spotcheck`, `reader-full` | The Reader through Groq | **needs a key** (`GROQ_API_KEY`) |

### Which commands were run, and what was left out

Every command in the table above, apart from the ones named here, was run in a clean clone of main without a key and exited 0, except where the table says otherwise. The exit codes and the notes are in docs/fresh_clone_report.md (run 8). An earlier run's codes are in `eval/results/readme_commands.json`. Some commands rewrite tracked files under `eval/results/`; see run 8.

- **Needs a key, not run:** `llm-test`, `reader-spotcheck`, `reader-full`.
- **Removed: `reader-score` (also `make eval-reader`).** It exits 1 until a person has filled in every human label, and the labels are not filled in. It was in this table before; it is removed so that every command listed exits 0. The scorer's own message names each unlabelled message.
- **Not run, by design:** `down` (stops the database), `ui` and `inbox` (servers that do not exit; `inbox` also runs `npm install`), `test` (the suite is the verification step: 959 passed, 0 failed, 1 xfailed on main).
- **Not included:** `false-positives` and `verify-frozen` are not in the Makefile or `make.ps1` because nothing implements them yet; a target that only prints "not built yet" would look like a feature. See `eval/results/makefile_gaps.md`.

Commands that the spec lists in §10.3 and that are not wired are in eval/results/makefile_gaps.md.

## Graph data model

As built, in FalkorDB 6.0.2 with one graph per organisation, `org_<id>` (docs/HEARTHGUARD.md §6.1; the schema and its unique keys are in core/graph/schema.py).

- **Trust graph:** `Org`, `Actor` (hashed id), `Action` (commit, review, issue, release), `Path` (how a release was made), `Privilege` (`merge`, `release`, `sign`, `npm_publish`), edges `DID`, `VIA`, `GRANTED`, `CAN_GRANT`, `APPROVED`.
- **Remembered normal:** `Normal` nodes (`cadence_days`, `active_keepers`, `usual_path`, `grant_days`; core/normal/metrics.py), each stored as of the time `T` it was computed for.
- **Claim graph:** `Source -[HAS]-> Span <-[FROM]- Claim <-[ASSERTED]- Actor` (core/claims/graph_write.py).
- **Agents and memory:** `Finding`, `Note`, `Task`, `AgentStep`, `Hardening`, `Exception` (the playbook), `OwnerDecision`.
- **Ecosystem graph** `ecosystem_<id>`: `Place`, `Identity`, `Role`, `Signal`, `Decision`, edges `EMITTED`, `RECORDED_IN`, `WATCHES`, `MADE_IN`, `SAME_AS` (packs/oss/ecosystem/graph.py). `Foundation`, `HOSTED_BY`, `Campaign` and `TOUCHES` are not written, because no public source in the cache names a hosting foundation for xz (eval/results/blockers_G.md).
- **Scratch graphs** made and dropped per call: `takeover_<run>`, `harden_<run>`, `redteam_<run>`.
- Every synthetic entity carries `synthetic: true`; planted ones carry `planted: true` and a `campaign_id`. Detectors never read those flags; only the scorer does.

## Queries and algorithms the product depends on

Every Cypher constant, with the module that runs it, is generated into [docs/queries.md](docs/queries.md); a test fails if that file is stale. The algorithms:

- `algo.SPpaths` over `OUTSIDER_ENTRY`, `CAN_GRANT`, `GRANTED` for takeover cost (core/takeover/cost.py), and over `VOUCHED_FOR`, `REVIEWED`, `GRANTED` for the trust path (core/takeover/trust_path.py).
- `algo.maxFlow` on a node-split projection for guardians (core/takeover/guardians.py).
- Plain code over graph reads for Vouch components (core/detectors/vouch.py).
- The time-filtered reads (`run_as_of`, core/graph/as_of.py) and the checked read path (`ro_query`, core/graph/ro_guard.py) go through `GRAPH.RO_QUERY` with an explicit timeout. The detector Cypher filters on `$T`, for example core/detectors/bypass.py.
- Other graph calls, such as the task board, the playbook and the claim writes, use the write-capable client with an explicit timeout (core/graph/client.py). They are not read-only.

## What is measured

Every number has its source file next to it. Where a result is unflattering it is shown as it was.

| Number | Value | Source |
|---|---|---|
| xz, per quarter | HOLD in all 10 quarters (2021-Q4 to 2024-Q1), reason "move unknown: RUSH, BYPASS" | eval/results/decision_status.json |
| Grant records found for xz | 0 (14 sources searched; one commit-message match was read and is not a grant) | eval/results/xz_grant_search.json |
| Red-team, tallowdate (synthetic), 200 campaigns | 182 caught, detection rate 0.91, median lead time 12.8 days | eval/results/redteam_tallowdate.json |
| Red-team, planted into a copy of xz history, 200 campaigns | 167 caught, detection rate 0.835, median lead time 11.0 days | eval/results/redteam_xz.json |
| Memory ablation, 100 campaigns | detection 0.88 with full memory, 0.82 with the last 90 days, 0.60 with the last 30. Clean campaigns flagged: 1 of 20 with full memory, 20 of 20 with either forgetful memory | eval/results/ablation_memory.json |
| Algorithm ablation, 100 campaigns | SPpaths off and maxFlow off tie the baseline (SPpaths is never called by the decision path). Vouch without components: detection 0.88 to 0.90, false alarms unchanged on a clean set that has no vouch claims | eval/results/ablation_algos.json |
| event-stream replay (2018) | First NOTE on 2018-09-16, 7.1 days AFTER the malicious release; 64.1 days before the public report. HOLD before that | eval/results/replay_event_stream.json |
| axios replay (2026) | Bypass did not fire: 33 of the 37 releases in the trailing 730 days were manual publishes, so a manual publish matched the remembered normal | eval/results/replay_axios.json |
| Hardening, scaffolded copy of xz history | Adding a second keeper raises guardians from 1 to 2 and lowers the caught campaigns from 167 to 152 of 200 (detection 0.835 to 0.76). This build does not explain that drop. The other two steps change neither takeover cost, guardians nor the caught count | eval/results/hardening_redteam_xz.json |
| Race test | 8 workers, 200 tasks, 0 duplicate claims, 40 notes for 40 findings | eval/results/race_run.json |
| Determinism | Identical findings under 5 task orderings | eval/results/determinism_run.json |
| Faults | All 9 failure types, including LLM offline, end in a bounded HOLD | eval/results/faults_run.json |
| Reader messages done | 94 of 240; 146 unread because the run stopped at the model's limit of 200000 tokens per day | eval/results/reader_full_progress.json |
| Reader precision and recall | NOT COMPUTED: no human labels yet | eval/results/reader_testset.json |

Three real attacks are too few to claim precision; the red-team numbers are on synthetic or planted campaigns and say nothing about how often a real project would be flagged.

## What is NOT COMPUTED, and why

- **Takeover cost and guardians on xz, over time:** the public git history holds no record of who was given release rights (eval/results/xz_grant_search.json).
- **Rush on xz:** no grant data. **Bypass on xz:** every release goes through one shared path.
- **Rush on the incident replays:** the npm registry records no grant event, so a newcomer's grant is placed at the first version that lists them, and Rush fires by construction of that record (eval/results/replay_event_stream.json, honesty notes).
- **Bypass on the removed axios versions:** the registry no longer serves them. Their path comes from one secondary write-up and is labelled secondary; the properties it does not state are NOT COMPUTED (eval/results/replay_axios.json).
- **Reader precision and recall:** no human labels yet.

## Limitations

- The xz backdoor was in the release tarballs, not in git. A git-based replay cannot show it (eval/results/xz_normal.json, notes).
- A NOT_FIRED result only covers the messages that were read. The Reader read 94 of 240 and found 3 claims; its recall is not measured.
- The frozen Bypass remembers 730 days. A two-year gap (event-stream) or a recent change of normal (axios) defeats it, and the replays show both.
- The registry-based incident graphs do not model a maintainer being removed; the replays stop at the incident date.
- Mail-only posters count as low-history under the spec's literal rule (docs/decisions/0004-mail-claims-in-org-xz.md).
- Every decision in docs/decisions/index.md is still open.
- Not built, or built only in part: see eval/results/completion_full.md for each row, and eval/results/blockers_*.md for the reason.

## Act II is synthetic

Act II, the `tallowdate` case, is synthetic: a fictional project, labelled SYNTHETIC wherever it appears (docs/HEARTHGUARD.md §3.5; `uv run python -m redteam.run_tallowdate`).

## AI disclosure

- Claude Code, an AI coding assistant, wrote most of the code and tests, under the owner's direction. Each AI-assisted step is logged in docs/AI_USE.md.
- A Haiku 5.5 subagent gave a blind AI second opinion on the test-set labels. It is labelled as an AI opinion everywhere it appears (docs/AI_USE.md).
- The Reader calls `openai/gpt-oss-20b` through Groq, for claim extraction only (eval/results/reader_full_run.json). No other product code calls an LLM.

## Tracks

Track entered: Track 02 — Agent Memory and Coordination (the name in docs/HEARTHGUARD.md and docs/submission_checklist.md; the event page is https://www.wemakedevs.org/hackathons/falkordb, listed in data/sources.yaml, and the name was not re-checked against it). The submission form has not been filled in yet.

## Docs

- Judge guide: [docs/judge_guide.md](docs/judge_guide.md)
- Cypher queries the product depends on, generated from the code: [docs/queries.md](docs/queries.md)
- Spec: [docs/HEARTHGUARD.md](docs/HEARTHGUARD.md)
- Project rules: [CLAUDE.md](CLAUDE.md)
- Decisions: [docs/decisions/index.md](docs/decisions/index.md)
- AI use log: [docs/AI_USE.md](docs/AI_USE.md)
- Submission checklist: [docs/submission_checklist.md](docs/submission_checklist.md)
- Blog outline: [docs/blog_outline.md](docs/blog_outline.md)
