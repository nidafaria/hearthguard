# Block C blockers

Written by the Block C agent (Haiku 5.5) on branch agent/block-c. Each row is not marked DONE.
A blocker names the row, the reason, and the exact command that failed or was not run.
"Not attempted" means the row was not started in this pass, not that a command failed.

| Row | Item | Reason | Command |
|---|---|---|---|
| 15 | Incident data for event-stream and axios ingested | Not attempted in this pass. Needs read-only GETs of public advisories, the npm registry JSON and the GitHub public API, cached under data/raw/ with URL, fetch time and status. | none yet (no fetch module written) |
| 39 | org graph: Hardening, Task, AgentStep | Depends on the task board (row 65), which is not built. Hardening nodes are not yet written to org graphs. | none |
| 65 | Task board with leases, stale-result rejection, requests | Not built. core/board is empty. | none |
| 69 | Guardrails: circuit breaker, bounded HOLD, re-plan limits | Not built. Depends on the Investigator (LLM planner) which is out of Block C's deterministic scope. | none |
| 76 | Working memory (AgentStep, task board) | Depends on row 65. | none |
| 78 | Memory ablation (`make ablation-memory`) | Not built. Block B's patience-curve screen (row 117) reads eval/results/ablation_memory.json, which does not exist. The scorer has the forgetful-memory function (redteam/score.py forget, judge_forgetful); the ablation runner and output file eval/results/ablation_memory.json are not written. | `make ablation-memory` (target still a placeholder) |
| 79 | Determinism, race and concurrency tests | Not built. tests/determinism and tests/race are empty. | `make verify-determinism`, `make race`, `make concurrency` (placeholders) |
| 81 | Resilience (`make faults`) | Not built. tests/faults is empty. | `make faults` (not in Makefile) |
| 82 | Algorithm ablation (`make ablation-algos`) | Not built. Needs a switch-off harness that does not edit frozen detectors. | `make ablation-algos` (placeholder) |
| 84 | event-stream and axios replays | Depends on row 15. | none |
| 85 | Hardening on xz and 10 false-alarm projects | The xz half is done (`eval/results/hardening_redteam_xz.json`, planted campaigns in a copy). The 10 false-alarm projects are not in the repo and no public cache for them exists under data/raw/. They are not invented. | `uv run python -m redteam.harden --n 200 --seed 7 --case xz` runs; the 10 projects: no source |
