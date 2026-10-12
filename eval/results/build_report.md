# Build report: Must list (Steps A to J)

Date 2026-10-12. Every number below comes from a saved file named beside it.

## What was built

| Step | Files |
|---|---|
| A | `eval/results/state_snapshot.json` |
| B | `eval/xz_grant_search.py`, `eval/results/xz_grant_search.json` |
| C | `eval/reader_full_run.py`, `eval/results/reader_full_run.json`, `reader_full_progress.json`; local only: `data/derived/reader_claims.json` (holds quotes, git-ignored) |
| D | `config/frozen.yaml` (thresholds from spec §7.1), `core/detectors/low_history.py`, `pressure.py`, `vouch.py`, `core/claims/graph_write.py`, `eval/xz_pressure_vouch_status.py`, `eval/results/pressure_vouch_status.json`, `tests/integration/test_pressure_vouch.py` (22 tests) |
| E | `eval/xz_quarterly_status.py`, `xz_quarterly_status.json`, `eval/xz_decision_status.py`, `decision_status.json`, `tests/unit/test_xz_decision_status.py` (6) |
| F | `eval/replay_xz.py`, `xz_replay.json`, `xz_replay.md`; `make replay CASE=xz` |
| G | `ui/` (React, Vite, TypeScript); `make ui` |
| H | `eval/demo.py`, `make demo`, `tests/unit/test_replay_demo.py` (6), `eval/results/final_tests.json` |
| I | `README.md`, `docs/decisions/index.md`, decisions 0004 to 0006, VERIFIED and AI_USE rows |

## Acceptance output

- Tests: 467 passed, 0 failed, 1 xfailed (`final_tests.json`). Before this work: 431 (`state_snapshot.json`).
- `docs/FREEZE.md` hash matches `docs/FREEZE.sha256`; Reader freeze version 1 still matches.
- `make.ps1 demo` run twice printed identical bytes (cmp, and a unit test that also blocks network use).
- `make ui` starts without a key and without FalkorDB (checked: dev server returns the page, serves `/results/xz_replay.json`, 404 for a missing file and for a path traversal; type check clean). The page was not opened in a browser by the agent.
- org_xz after the claim write: 4,569 actions, 69 actors (1 mail-only), 3 claims. The 68 git actors and all other counts are unchanged.

## Differences from the spec, and why

1. **Step C is incomplete.** The daily limit of 200,000 tokens stopped the run at 94 of 240 messages (`reader_full_progress.json`: 146 remaining, next msg00507). The 60 test-set messages are deliberately not read (they are for human labels). The Reader prompt was not touched.
2. **Messages the Reader cannot read** are recorded, not cut or retried: 4 are too long for one request under the 8,000 tokens-a-minute limit (`reader_full_run.json`).
3. **`config/frozen.yaml` was a placeholder.** I filled it with the numbers in §7.1; it is not hashed by any target yet (`verify-frozen` does not exist).
4. **Vouch components** are found in plain code over the SHARES edges read from the graph, not with `algo.WCC` in the database. Nothing depends on the difference today, because no SHARES edge exists.
5. **Pressure** computes only the claim condition; the keeper condition is OPEN (decision 0005). It returns NOT_FIRED when the claim condition fails and NOT_COMPUTED when it holds. It never returns FIRED on real data.
6. **Mail posters are written into org_xz** as Actors (decision 0004). This is my choice and is OPEN.
7. **The UI** reads files only; it shows the replay, the status and reason per detector, the query text and its run time, and NOT COMPUTED where a file is missing. It is a minimal page, not a designed product.
8. The first Reader attempt crashed on two kinds of message (too long; model returned invalid JSON). I fixed the script to record them, and reran. No prompt change.

## Results (all provisional)

- Grant records: 0 in 14 sources (`xz_grant_search.json`) => Privilege and GRANTED not added.
- Reader on 94 messages: 3 claims (all CAPACITY_STATEMENT), 6 rejected quotes, 4 not read (`reader_full_run.json`).
- Pressure and Vouch: NOT_FIRED in all 10 quarters, on the messages read only (`pressure_vouch_status.json`; the page and `xz_replay.md` show unread counts per quarter).
- Decision: HOLD in all 10 quarters, reason "move unknown: RUSH, BYPASS" (`decision_status.json`).
- Pressure and Vouch did not fire because the Reader returned no PRESSURE, URGENCY or VOUCH claim, and its recall is not measured. A quiet Reader and an absent signal look the same here.

## OPEN decisions

See `docs/decisions/index.md`: 0001, 0002, 0003 (earlier), 0004, 0005, 0006 (new).

## NOT COMPUTED

Takeover cost, guardians, Rush, Bypass, Lone keeper (no grant data; one shared path); Pressure's keeper condition; Vouch (no candidate, no SHARES); Reader precision and recall (no human labels); 146 of 240 Reader messages.

## What the demo shows, and does not

It shows ten quarter-ends with the normal metrics and honest NOT COMPUTED cells, and a HOLD decision. It does **not** show the backdoor being found, a working takeover cost, or a fired detector; the public data holds no grant record, and the git history does not contain the backdoor.
