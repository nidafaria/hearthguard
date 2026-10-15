# Makefile gaps

Targets that still print "not built yet" and exit 1, with the reason. Nothing was added to make them
work: no command in the repo produces their result.

| Target | Reason |
|---|---|
| `false-positives` | No module or script computes a false-positive rate on its own. The nearest results are the clean-campaign counts inside `eval/results/ablation_memory.json` and `redteam_*.json`, which `make ablation-memory` and `make redteam` write. A separate census-based false-positive run (spec 10.2) has not been written. |
| `verify-frozen` | No module checks the frozen files against `docs/FREEZE.sha256`. Writing one is new behaviour, and `docs/FREEZE.md` and its hash are not edited. |

## Wired in this change

| Target | Command | Note |
|---|---|---|
| `ablation-memory` | `uv run python -m eval.ablation_memory` | Needs the FalkorDB container. |
| `ablation-algos` | `uv run python -m eval.ablation_algos` | Needs the FalkorDB container. |
| `eval-reader` | `uv run python -m eval.reader_score` | Refuses (and names the rows) until a person has filled in every human label. |
| `verify-determinism` | `uv run python -m eval.verify_determinism` | Needs the FalkorDB container. |
| `race` | `uv run python -m eval.race` | Needs the FalkorDB container. |

## Modules with no target at all

`eval.chaos`, `eval.faults`, `eval.verify_learning`, `eval.verify_packs` and `eval.concurrency` exist but
have no Makefile target. They never printed "not built yet", so they were not wired here.
