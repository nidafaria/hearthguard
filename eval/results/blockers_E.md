# Blockers, block E

Rows left PARTIAL or NOT STARTED, and why. Each names the command that shows it and what would unblock it.

## Row 43 · §6.5 · playbook graph · PARTIAL
- Built: `core/playbook/store.py` writes the `playbook` graph: DetectorSpec hash, Exception nodes with state, agreements and gate numbers. No org data (tests/integration/test_learning_store.py).
- Missing: compiled investigation plans (spec 6.5, 13.10 "compiled plans with LLM calls saved").
- Shows it: `grep -rn "Plan" core/playbook` (nothing).
- Unblock: a plan compiler, which needs the LLM allowance or a deterministic template. Not started.

## Row 66 · §8.3 · Learned exceptions with safety rules and regression gate · PARTIAL
- Built: deterministic filler, template schema, four safety rules, regression gate, four end states (tests/unit/test_learning_*.py, 39 passing). Evidence: eval/results/learning_verify.json, learning_chaos_seed*.json.
- Missing:
  - Adopted does not act. No exception changes a live decision. Applying it needs actor-level move evidence, which the saved suite lacks (and the frozen detectors do not carry).
  - The gate uses a worst-case replay on the saved suite (decision 0007). It does not replay the planted campaigns through the detectors on the graph.
  - The LLM proposal in spec 8.3 step 2 is replaced by the fixed filler (decision 0007). That is a deliberate deviation, and the spec owner should accept it.
  - Real-case rows are all HOLD in the saved files, so the real-case check cannot lose anything.
- Unblock: the owner accepts decision 0007; a per-actor move record in the saved suite (or a regenerated suite with actor ids) so the gate can run exactly.

## Row 80 · §10.2 · Learning proof (`verify-learning`, `chaos`) · PARTIAL
- Built: `eval/verify_learning.py` and `eval/chaos.py`. Both run. Seeds 1, 2, 3, 4, 5, 7 and 42 gave: Shadow for bots (zero planted lost), Rejected for vendor contact change (22 lost) and company handover (18 lost).
- Missing:
  - The `make verify-learning` and `make chaos` targets are not in the Makefile (the lead wires them).
  - Seeds 1-4 all draw the bots pattern, so they give the same exception id. The brief says "a different seed yields a different exception". The template holds no org data, so two seeds with the same pattern cannot differ in the template. This contradicts the brief as written.
- Shows it: `uv run python -m eval.chaos --seed 1` and `--seed 5`.
- Unblock: the spec owner decides whether "different exception" means a different pattern.

## Row 102 · §12.2 · Simulate a fix button · PARTIAL (unchanged)
- Blocker: a saved red-team file now exists (`eval/results/hardening_redteam_xz.json`, block C) with per-step caught counts and median lead time. The live simulate could read it.
- Conflict: `tests/integration/test_inbox_loop.py` lines 181-184 assert `red_team_file is None` and `NOT COMPUTED` for xz. Making caught and lead time computed breaks that expectation. The brief forbids editing an existing test expectation, so I stopped.
- Shows it: `uv run pytest tests/integration/test_inbox_loop.py::test_simulate_runs_live_and_leaves_the_org_graph_unchanged`.
- Unblock: the owner decides that test's premise (no saved red-team file) is out of date, and changes the expectation. Then `simulate_fix.find_red_team` can accept the `steps` shape with `campaigns.before/after`.

## Row 104 · §12.2 · It's fine button and learning result in thread · PARTIAL
- Built: the dismiss route runs the learning step and returns the result; the thread shows it (tests/integration/test_learning_thread.py, 8 passing). The OwnerDecision already existed (record_dismissal, via liaison.dismiss).
- Missing:
  - The browser check against the local app (eval/results/fine_browser_check.json). Not run in this block.
  - The result is not applied anywhere (see row 66).
- Unblock: run `make up` and the UI, do the browser check, write the JSON.

## Row 120 · §13.10 · Playbook screen · PARTIAL
- Built: `ui/src/Playbook.tsx`, route `#/playbook` in `ui/src/App.tsx`. `tsc --noEmit` is clean; vitest 31 pass (existing tests). No test covers the Playbook screen itself.
- Missing: a browser check, and compiled plans with LLM calls saved (spec 13.10 item 10).
- Unblock: browser check; plans (row 43).

## Not touched, outside block E
- `ruff check .` reports 42 findings in `eval/video_check.py` and `eval/blog_check.py`; `ruff format --check` flags 6 files including `eval/completion_full.py` and `core/hardening/xz.py`. None are block E files.
- `.env` is not in this worktree. Tests run with the `FALKORDB_PORT=6382` environment variable, as the brief says. The HASH_SALT tests are skipped (they skip without a salt, as they do on main).
