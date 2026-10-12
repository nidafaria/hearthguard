# Hearthguard

> Some attacks are too slow for anything that forgets.

Hearthguard keeps a memory of who could change an open-source project, and how that changed over time. It stores that memory as a graph in FalkorDB (docs/HEARTHGUARD.md §5).

It was built to ask one question: would this memory have flagged the xz backdoor, using only public data? In this build, it does **not** detect the xz backdoor, and it does not claim to.

**Status: provisional. The project is not complete.** The rules are not frozen yet. Of 131 planned rows, 20 are DONE, 25 are PARTIAL and 86 are NOT STARTED (eval/results/completion_full.md).

## Run the demo

The demo needs no API key, no network and no database. It prints a table built from saved result files. Two runs printed identical bytes (eval/results/build_report.md).

Windows (no `make` needed):

```powershell
uv sync
.\make.ps1 demo
```

Linux or macOS with GNU make: `make demo`. I could not run this here, because `make` is not installed on this machine. See "Known issues".

The direct command also works: `uv run python -m eval.demo`. I ran it on Windows and it printed the table.

## Commands

Each name works as `make <name>`, or on Windows as `.\make.ps1 <name>`.

| Command | What it does | Needs | Source |
|---|---|---|---|
| `up` / `down` | Start or stop FalkorDB. The image is pinned to `falkordb/falkordb:6.0.2`. If a port is taken, set `FALKORDB_PORT` or `FALKORDB_UI_PORT` in `.env` | Docker | docker-compose.yml |
| `test` | Run the test suite (pytest) | uv | Makefile |
| `lint` | Run ruff check and format check | uv | Makefile |
| `smoke-algos` | Re-check each FalkorDB procedure the product depends on | FalkorDB | Makefile |
| `schema-test` | Schema, as-of helper, read-only guard and hashing tests | FalkorDB | Makefile |
| `ingest-xz` | Build `org_xz` from the public xz git history | FalkorDB | Makefile |
| `normal-xz` | Normal metrics at each quarter-end | FalkorDB | Makefile; eval/results/xz_normal.json |
| `takeover-xz` | Takeover cost status for xz. It is NOT COMPUTED | FalkorDB | Makefile; eval/results/xz_takeover_status.json |
| `detectors-xz` | Rush, Bypass and Lone keeper status for xz | FalkorDB | Makefile |
| `cache-mail-xz`, `cache-github-xz`, `cache-inventory-xz` | Cache public data to `data/raw/` (git-ignored) | network; `GITHUB_TOKEN` is faster | Makefile; CLAUDE.md |
| `llm-test` | One live call to the extraction model | `GROQ_API_KEY` | Makefile |
| `reader-spotcheck` | The Reader on 20 fixed messages | `GROQ_API_KEY` | Makefile; eval/results/reader_spotcheck.json |
| `reader-testset` | Pick the 60 held-back messages and write the labelling sheet | see Makefile comment | Makefile; eval/results/reader_testset.json |
| `reader-score` | Score the Reader against human labels. It stops if labels are missing | human labels | Makefile |
| `reader-full` | The Reader on the in-scope messages. Stops at the daily token limit and resumes on the next run | `GROQ_API_KEY` | Makefile; eval/results/reader_full_progress.json |
| `pressure-vouch-xz` | Write claims to `org_xz`, then Pressure and Vouch per quarter | FalkorDB | Makefile |
| `quarterly-xz` | Rush, Bypass, Lone keeper, takeover cost and guardians per quarter | FalkorDB | Makefile |
| `decision-xz` | The decision policy on the saved statuses | files only | Makefile |
| `replay CASE=xz` | Rewrite `eval/results/xz_replay.json` and `.md` from saved files | files only | Makefile |
| `ui` | Read-only page at http://localhost:5173. First run installs npm packages | Node, npm | Makefile; ui/vite.config.ts |
| `demo` | Print the replay table | files only | Makefile |

The proof commands in the spec that are not built yet (docs/HEARTHGUARD.md §10.3) are left out of this list. They are not in the Makefile.

## Graph data model

As built. The full plan is in docs/HEARTHGUARD.md §6.1.

- `Org`, `Actor` (hashed id), `Action` (commit, release), `Path`, `Normal` (packs/oss/xz_graph.py; eval/results/completion_full.md, rows 2 and 32).
- `Source -[HAS]-> Span <-[FROM]- Claim <-[ASSERTED]- Actor`, written from the Reader (core/claims/graph_write.py; eval/results/completion_full.md, row 33).
- Edges `DID`, `VIA` and `OF`.
- No `Privilege` or `GRANTED` edge exists, because no grant is evidenced (eval/results/build_report.md).

Every query the status files ran, with its run time, is in `eval/results/pressure_vouch_status.json` and `eval/results/xz_quarterly_status.json`. The README lists only two key queries today. The full list is still PARTIAL (eval/results/completion_full.md, row 5).

## What is measured

Every number below has its source file next to it.

| Number | Value | Source |
|---|---|---|
| Tests | 467 passed, 0 failed, 1 xfailed (recorded at commit 796ac40) | eval/results/final_tests.json |
| Grant records found for xz | 0. 14 sources were searched. One commit-message match was read; it is a sorting change, not a grant | eval/results/xz_grant_search.json; eval/results/build_report.md |
| Quarter-ends replayed | 10, from 2021-Q4 to 2024-Q1 | eval/results/decision_status.json; eval/results/build_report.md |
| Decision per quarter | HOLD in all 10 quarters, reason "move unknown: RUSH, BYPASS" | eval/results/decision_status.json |
| Pressure and Vouch per quarter | NOT_FIRED in all 10 quarters, on the messages the Reader read only | eval/results/pressure_vouch_status.json |
| Reader messages in scope | 240. Another 60 are held back for human labels | eval/results/reader_full_run.json; eval/results/reader_testset.json |
| Reader messages done | 94 of 240: 90 read, and 4 recorded as too long to read | eval/results/reader_full_progress.json; eval/results/pressure_vouch_status.json |
| Reader claims | 3, all CAPACITY_STATEMENT. 6 quotes rejected because they were not exact text | eval/results/reader_full_run.json |
| Reader tokens | 110,366 in, 44,479 out, of which 42,803 were reasoning | eval/results/reader_full_run.json |
| Reader spot check | 20 messages, 0 claims, 1 rejected quote | eval/results/reader_spotcheck.json |
| org_xz graph | 4,569 actions, 69 actors (68 from git, 1 from mail only), 3 claims | eval/results/build_report.md |

## The Reader

- **The free model allowance limited the Reader run to 94 of 240 messages.** The model is `openai/gpt-oss-20b`. The run stopped at the daily limit of 200,000 tokens (eval/results/reader_full_progress.json). 146 messages remain unread.
- **The Reader was not measured against human labels.** Its precision and recall are NOT COMPUTED. The 60 held-back messages have no human labels yet (eval/results/reader_testset.json; eval/results/build_report.md).
- **The Haiku labels are an AI second opinion.** They are in eval/results/reader_labels_haiku.csv. They are not human labels and not ground truth (docs/AI_USE.md).
- The Reader does not decide anything. The LLM is never in the decision path (docs/HEARTHGUARD.md §8.4).

## What is NOT COMPUTED, and why

- **Takeover cost and guardians (xz, over time):** the public git history and the cached GitHub data hold no record of who was given commit or release rights (eval/results/xz_takeover_status.json; eval/results/xz_grant_search.json).
- **Rush:** there is no `Privilege` of kind "release", so there are no grant data (eval/results/decision_status.json).
- **Bypass:** every xz release goes through one shared path, so there is nothing to compare (eval/results/decision_status.json).
- **Lone keeper:** it depends on guardians, which are NOT COMPUTED (eval/results/build_report.md).
- **Pressure's keeper condition:** the rule is still open (docs/decisions/0005-pressure-keeper-activity-open.md). Pressure can only be NOT_FIRED or NOT_COMPUTED.
- **Vouch:** no candidate exists, and no SHARES edge can be built from the public record (docs/decisions/0004-mail-claims-in-org-xz.md; eval/results/decision_status.json).
- **Reader precision and recall:** no human labels yet (eval/results/build_report.md).
- **146 of 240 Reader messages:** not read. The free model allowance stopped the run (eval/results/reader_full_progress.json).

## Limitations

- The xz backdoor was in the release tarballs, not in git. This git-based replay cannot show it (eval/results/xz_normal.json, notes).
- A NOT_FIRED result only covers the messages that were read. The Reader found 3 claims in 94 messages, and its recall is not measured (eval/results/pressure_vouch_status.json; eval/results/reader_full_run.json).
- Mail-only posters count as low-history under the spec's literal rule (docs/decisions/0004-mail-claims-in-org-xz.md).
- Every decision in docs/decisions/index.md is still open.
- The takeover cost, guardians, hardening simulator, Slack loop, MCP servers, finance pack and census are not built (eval/results/completion_full.md).
- Everything here is provisional until the freeze is signed. docs/FREEZE.md is a draft (eval/results/completion_full.md, row 77).

## Act II is synthetic

Act II, the `tallowdate` case, is synthetic. It is not built yet, and no output for it exists (docs/HEARTHGUARD.md §3.5; eval/results/completion_full.md, row 16).

## AI disclosure

- Claude Code, an AI coding assistant, wrote most of the code and tests, under the owner's direction. Each AI-assisted step is logged in docs/AI_USE.md.
- A Haiku 5.5 subagent gave a blind AI second opinion on the test-set labels. It is labelled as an AI opinion everywhere it appears (docs/AI_USE.md).
- The Reader calls `openai/gpt-oss-20b` through Groq, for claim extraction only (Makefile; eval/results/reader_full_run.json).

## Tracks

Track entered: Track 02 — Agent Memory and Coordination (the name on the event page, https://www.wemakedevs.org/hackathons/falkordb). The submission form has not been filled in yet.

## Known issues

- `make` is not installed on the machine used to check this README. The `make` targets were checked against `make.ps1` and the Makefile by reading both, and by running the Windows route. The Makefile had duplicate `demo` and `replay` rules, which are now removed.
- The judge path and its expected outputs are in [docs/judge_guide.md](docs/judge_guide.md).

## Docs

- Judge guide (about half an hour, not timed, with expected outputs): [docs/judge_guide.md](docs/judge_guide.md)
- Spec: [docs/HEARTHGUARD.md](docs/HEARTHGUARD.md)
- Project rules: [CLAUDE.md](CLAUDE.md)
- Decisions: [docs/decisions/index.md](docs/decisions/index.md)
- AI use log: [docs/AI_USE.md](docs/AI_USE.md)
- Submission checklist: [docs/submission_checklist.md](docs/submission_checklist.md)
- Blog outline: [docs/blog_outline.md](docs/blog_outline.md)
