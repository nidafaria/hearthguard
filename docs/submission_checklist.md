# Submission checklist

Status is one of DONE, PARTIAL or NOT STARTED. Each row has its rule source and the evidence in this repo.

Deadline: Oct 18, about 6:00 PM IST (docs/HEARTHGUARD.md §1).

## Event rules (docs/HEARTHGUARD.md §1)

| # | Rule | Status | What is done | What is needed | Evidence |
|---|---|---|---|---|---|
| 1 | R2/R3: FalkorDB must be load-bearing | PARTIAL | Detectors and the Reader write to FalkorDB. The image is pinned to 6.0.2 | The replay and demo read saved JSON, not the graph. Vouch components are plain Python. A judge could read this as "the graph is decoration" | eval/results/build_report.md, item 4; docker-compose.yml |
| 2 | R6: public, synthetic or own data only; identifiers hashed | DONE | Ids hashed on ingest. Only public xz data is used. Raw cache is git-ignored | Synthetic label for the Act II case when it is built | eval/results/completion_full.md, row 2 |
| 3 | R10: public repo | NOT STARTED | Repo is local only | Create a public remote and push. Check that no secret is in the history | eval/results/completion_full.md, row 3 |
| 4 | R10: README with setup and graph data model | PARTIAL | README.md has setup, the demo, the commands and the data model | Test the setup on a clean machine. Confirm `make demo` works on the judge's platform | README.md; eval/results/completion_full.md, row 4 |
| 5 | R10: the Cypher queries the product depends on | PARTIAL | Two key queries in README.md. Every query run is saved in the status files | List every query the product depends on, in one place | eval/results/completion_full.md, row 5 |
| 6 | R10: live deployment or complete local setup | PARTIAL | Local setup: `docker compose up`, then the demo with no key. `uv run python -m eval.demo` ran | No live deployment. Test the local setup from a clean checkout | eval/results/completion_full.md, row 6; eval/results/build_report.md |
| 7 | R10: demo video | NOT STARTED | None | A video of 3 minutes or less, in the two-act structure | docs/HEARTHGUARD.md §14; eval/results/completion_full.md, row 129 |
| 8 | R10 and R5: tracks named (Track 02 listed first) | NOT STARTED | Planned mapping in the spec | The owner picks the tracks. The README and the form must name them | docs/HEARTHGUARD.md §19; eval/results/completion_full.md, row 9 |
| 9 | R11: AI assistance disclosed | DONE | AI disclosure section in README.md. Each AI step logged | Keep the log up to date. Add an entry for this writeup step (see Open issues) | README.md; docs/AI_USE.md; eval/results/completion_full.md, row 7 |
| 10 | R12/R13: named owners who can explain each module; decisions recorded | PARTIAL | Decisions 0001 to 0006 in docs/decisions/. Every decision is still open | Name an owner for each module. Each owner writes down how their module works | docs/decisions/index.md; eval/results/completion_full.md, row 8 |
| 11 | Submission form and track mapping | NOT STARTED | Track text exists in the spec | Fill in the form using the track mapping | docs/HEARTHGUARD.md §19; eval/results/completion_full.md, row 131 |
| 12 | Submit by the deadline | NOT STARTED | Nothing submitted | Submit before the deadline above | docs/HEARTHGUARD.md §1 |

Judging criteria are not published for this event (docs/HEARTHGUARD.md §1). This is a note, not a checklist item.

## Pitch items (docs/HEARTHGUARD.md §14, §20; completion list)

| # | Item | Status | What is needed | Evidence |
|---|---|---|---|---|
| 13 | README, final: claim, commands, model, queries, measured numbers, limits, AI use | PARTIAL | This README has all of these. The owner must review it, and every number must still match its source file | README.md; eval/results/completion_full.md, row 128 |
| 14 | Blog post (side prize) | NOT STARTED | The outline is written (docs/blog_outline.md). The post is not | Publish on dev.to or Hashnode, and link it from the README. eval/results/completion_full.md, row 130 |

## Open issues found while writing this

- **`make demo` may fail on Linux and macOS.** The Makefile has two recipes for `demo`. The "not built yet" placeholder at the bottom is the last one, so GNU make would likely use it. `make` is not installed here, so this is untested. The fix is in the Makefile (out of scope for this step).
- **The old README had numbers without a source.** "4,569 actions" had no file. It is now in eval/results/build_report.md. The "8,000 tokens a minute" limit in build_report.md has no matching field in eval/results/reader_full_run.json, so it is left out.
- **The old README named a model for Claude Code.** No file in the repo names it, so the new README does not.
- **Grant search.** The result is 0 grant records, from 14 sources (eval/results/xz_grant_search.json; eval/results/build_report.md). One commit-message match was read and found not to be a grant. The README says so, rather than saying "0 in 14 sources" with nothing else.
- **This step is not in docs/AI_USE.md.** CLAUDE.md asks for one line per AI step. The scope of this step allowed edits to three files only, so the line was not added.
