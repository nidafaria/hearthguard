# Blockers, block B

## Row 117: Patience curve (spec 13.7)

- Status: stays PARTIAL.
- Reason: the chart reads `eval/results/ablation_memory.json`, which block C writes (detection rate and lead time against attacker patience, full versus forgetful memory). That file is not on this branch, so the panel shows NOT COMPUTED and names the blocker. No curve is drawn from any other data.
- Command that would produce the input: `make ablation-memory` (still a placeholder in the Makefile, so it exits 1 with "ablation-memory: not built yet").
- Unblock: merge block C's `ablation_memory.json` onto main, then the screen will still need a chart over its schema (`ui/src/Patience.tsx` currently reports presence only).

## Row 4: README with setup and graph data model

- Status: stays PARTIAL.
- Done here: the README lists the new commands (gaps, demo sections, connect), links docs/queries.md, and the query list is generated from code.
- Still open: the judge path needs the full suite to run from a clean clone, and that needs FalkorDB, which a judge may not have running (see row 6).

## Row 6: Live deployment or complete local setup

- Status: stays PARTIAL.
- Command that fails in a clean clone (no `.env`, no `data/raw/`, no FalkorDB): `powershell -ExecutionPolicy Bypass -File eval\fresh_clone_test.ps1 -WithTests`. The full `make test` step reports `redis.exceptions.AuthenticationError` and `ConnectionError` from the FalkorDB-backed tests. Those need a running FalkorDB, which the README states.
- Command that fails in lint in a clean clone: `uv run ruff check .`. The failing files are eval/video_check.py, eval/blog_check.py and eval/completion_full.py (its loader hook is the text the brief specified, with E402 and I001 on it). eval/video_check.py and eval/blog_check.py belong to other blocks.
- Git-ignored data no longer breaks tests: the ecosystem and xz ingest modules, and the salt-dependent unit tests, skip with a reason. See docs/fresh_clone_report.md, run 3.
