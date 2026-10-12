# Hearthguard

> Some attacks are too slow for anything that forgets.

Hearthguard is a trust memory for organisations. It is being built for the Graph Hacks hackathon (WeMakeDevs × FalkorDB). The full spec is in [docs/HEARTHGUARD.md](docs/HEARTHGUARD.md). Project rules are in [CLAUDE.md](CLAUDE.md). This README is provisional: the rules are not yet frozen (docs/FREEZE.md is a draft).

## The one-page claim

Replay of the public xz history (git plus the xz-devel mailing list, 2021 to 2024), one row per quarter-end, built from saved result files only. **It does not detect the xz backdoor, and it does not claim to.** What it shows today:

- The normal metrics (commit cadence, active keepers) compute for every quarter: `eval/results/xz_normal.json`.
- Takeover cost, guardians, Rush, Bypass and Lone keeper are **NOT COMPUTED** for every quarter, because the public git history holds no record of who was given commit or release rights (`eval/results/xz_grant_search.json`: 0 records in 14 sources) and every release shares one path.
- Pressure and Vouch ran on the messages the Reader had read (90 of 240 at the time of this run, plus 4 recorded as too long to read) and found no PRESSURE, URGENCY or VOUCH claim. That is **NOT_FIRED on those messages**, not a clean result for the rest (`eval/results/pressure_vouch_status.json`).
- The decision for all 10 quarters is **HOLD** ("move unknown: RUSH, BYPASS"): `eval/results/decision_status.json`.

## Setup (local)

```bash
cp .env.example .env          # fill in values locally; .env is git-ignored
make up                       # FalkorDB on localhost (pinned falkordb/falkordb:6.0.2)
uv sync                       # Python 3.11+ environment
make lint
make test                     # 467 passed, 1 xfailed (eval/results/final_tests.json)
make down
```

On Windows without `make`, run `.\make.ps1 up`, `.\make.ps1 test`, and so on. If port 6379 is in use, set `FALKORDB_PORT` in `.env`.

## See it: no key, no network, no database

```bash
make demo                     # prints the replay table from saved results; identical every run
make ui                       # read-only page at http://localhost:5173 (first run: npm install)
make replay CASE=xz           # rewrites eval/results/xz_replay.json and .md from the saved files
```

## Commands

| Command | What it does | Needs |
|---|---|---|
| `make ingest-xz`, `normal-xz`, `takeover-xz`, `detectors-xz` | Build org_xz from git; normal metrics; takeover and detector status at 2024-03-31 | FalkorDB |
| `make cache-mail-xz`, `cache-github-xz` | Cache public mailing-list and GitHub data to `data/raw/` | network, GITHUB_TOKEN |
| `make reader-full` | Frozen Reader on the in-scope messages; resumes after the daily limit | GROQ_API_KEY |
| `make pressure-vouch-xz` | Claims into org_xz, then Pressure and Vouch per quarter | FalkorDB |
| `make quarterly-xz` | Rush, Bypass, Lone keeper, takeover cost, guardians per quarter | FalkorDB |
| `make decision-xz` | The decision policy on the saved statuses | files only |
| `make reader-testset`, `make reader-score` | Hand-labelled Reader test set and its scorer | see `eval/results/reader_labelling_guide.md` |

## Graph data model (spec §6.1, as built)

`Actor` (hashed id), `Action` (commit, release), `Path`, `Org`, `Normal`; and, from the Reader, `Source -[HAS]-> Span <-[FROM]- Claim <-[ASSERTED]- Actor`. Edges `DID`, `VIA`, `OF`. org_xz now holds 4,569 actions, 69 actors, 3 claims (`python -c` over `xz_graph.graph_counts`; the 68 git actors plus 1 mail-only actor, see docs/decisions/0004). No `Privilege` or `GRANTED` exists, because none is evidenced.

## Key queries

- Pressure claims (`core/detectors/pressure.py`): `MATCH (a:Actor)-[:ASSERTED]->(c:Claim) WHERE c.kind IN $kinds AND c.at <= $T AND c.at > $start RETURN a.hid, c.id, c.kind, c.at`.
- Low history (`core/detectors/low_history.py`): first-seen and `count` of `DID` edges at or before `$T`.
- Every query, with its run time, is in `eval/results/pressure_vouch_status.json` and `xz_quarterly_status.json`, and shown in the page.

## What is measured, with its source file

| Number | Value | Source |
|---|---|---|
| Tests | 467 passed, 0 failed, 1 xfailed | `eval/results/final_tests.json` |
| Grant records found for xz | 0 of 14 sources | `eval/results/xz_grant_search.json` |
| Messages the Reader has read | 94 of 240 done (3 claims, all CAPACITY_STATEMENT; 6 rejected quotes; 4 too long) | `eval/results/reader_full_run.json` |
| Messages held back for human labels | 60 | `eval/results/reader_testset.json` |
| Reader token use so far | 110,366 in, 44,479 out, 42,803 of the output was reasoning | `eval/results/reader_full_run.json` |
| Spot check: claims in 20 messages | 0 (and one clear miss) | `eval/results/reader_spotcheck.json`, `reader_handcheck.md` |

The Reader's **precision and recall are NOT COMPUTED**: the 60-message test set has no human labels yet. The Haiku labels in `eval/results/reader_labels_haiku.csv` are an AI second opinion, not a human review and not ground truth.

## NOT COMPUTED, and why

- **Takeover cost, guardians, Rush, Lone keeper**: no grant record in public data.
- **Bypass**: the xz git ingest gives every release one shared path, so there is nothing to compare.
- **Pressure's keeper condition**: open in the freeze (docs/decisions/0005). Pressure is only ever NOT_FIRED or NOT_COMPUTED.
- **Vouch**: the Reader does not extract the candidate, and no SHARES edge can be built from the public record (docs/decisions/0004).
- **Reader recall and precision**: no human labels yet. **146 of 240 messages** are still unread (daily token limit of 200,000).

## Limitations

The xz backdoor was in release tarballs, not in git, so these numbers cannot show it. The Reader found almost nothing (3 claims in 94 messages) and missed a message on the spot check; its recall is unmeasured. Mail-only posters count as low-history by the spec's literal rule. Everything is provisional until the freeze is signed.

## AI disclosure

Claude Code (Sonnet 5.5) wrote most of the code and tests under the owner's direction; each step is logged in [docs/AI_USE.md](docs/AI_USE.md). The Reader uses `openai/gpt-oss-20b` through Groq for extraction only; the LLM is never in the decision path. A Haiku 5.5 subagent gave a blind AI second opinion on the test-set labels; it is labelled as such everywhere.

## Open decisions

See [docs/decisions/index.md](docs/decisions/index.md).
