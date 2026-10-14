# Block G: open items

## Row 40: ecosystem_<id> graph (stays PARTIAL)

- Missing: `Foundation`, `HOSTED_BY`, `Campaign`, `TOUCHES` (spec §6.2).
- Why: `HOSTED_BY` needs a public source that names the foundation hosting xz. None is in the cache
  (`data/raw/ecosystem/`), so writing the edge would invent one. `Campaign` and `TOUCHES` would
  have to be derived from a detector decision, and the xz decision is HOLD in every quarter
  (`eval/results/decision_status.json`), so there is no campaign to record.
- Command that shows it: `uv run python -m eval.ecosystem_xz`, then
  `MATCH (n) RETURN DISTINCT labels(n)` on `ecosystem_xz` lists no Foundation or Campaign.
- Unblock: a cached public page that names the hosting foundation (for the OpenJS alert, the
  foundation names a different project), and a decision on what a Campaign is for a case where
  nothing fired.

## Row 6: Live deployment or complete local setup (stays PARTIAL)

- Missing: a run from a clean clone that passes the whole suite. The FalkorDB-backed tests need a
  running database and `.env` with `HEARTHGUARD_HASH_SALT`; the README states both.
- Command that shows it: `powershell -ExecutionPolicy Bypass -File eval\fresh_clone_test.ps1
  -WithTests` (not re-run in this block).
- Unblock: a live deployment, or a decision that the stated local setup is enough.

## Row 128: README, final (stays PARTIAL)

- Missing: the demo video link (the video is not recorded) and the submission form entry.
- Done here: claim, setup, command table, graph model, queries and algorithms, measured numbers
  with sources, limits, AI use and tracks (README.md; tests/integration/test_incidents_readme.py).
- Unblock: record the video and add its link.

## Data notes (not blockers)

- `data/raw/incidents/` is git-ignored. `uv run python -m eval.incidents_fetch` recreates it from
  public URLs; the integration tests skip with that reason when it is absent.
- The removed axios versions have no registry record. Their path comes from one secondary write-up
  (labelled secondary in the graph and the replay).
