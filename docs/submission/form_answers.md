# Submission form answers (ready to paste)

I fetched https://www.wemakedevs.org/hackathons/falkordb/rules on 2026-10-18. The page lists what a submission must contain (Rule 10) but **not** the form's own field names; the form itself loads only after login ("Loading…"). The fields below follow Rule 10 plus the usual form items. Match them by meaning when you see the real form. Replace every `<<...>>` with a real link or fact before you paste. Nothing here has been submitted.

## Project name
Hearthguard

## One-line description (paste)
Hearthguard keeps a graph memory in FalkorDB of who could change an open-source project and how that changed over time, and reads four slow trust-takeover moves from it with plain, tested code.

## Short description (about 120 words, paste)
Some attacks are too slow for anything that forgets. Hearthguard stores who holds the keys to a project, how fast trust was granted in the past, and what "normal" looked like at each quarter-end, as a time-aware graph in FalkorDB 6.0.2. Plain code reads four slow moves from it (Pressure, Vouch, Rush, Bypass) and one multiplier (Lone keeper). A language model only reads messages into typed claims; it never decides. We replayed it on the public xz history. It does not detect the xz backdoor and does not claim to: the public record has no grant of release rights, so the decision is HOLD in all 10 quarters and takeover cost is NOT COMPUTED. We report every number with its source file, and say NOT COMPUTED where we cannot check.

## Track(s) entered
**Track 02: Agent Memory and Coordination.**
(The rules page names three tracks: "Agents That Act on Connected Data", "Agent Memory and Coordination", "Company Brain". Teams may enter several, but must name each. The project spec also lists Track 01 and Track 03 as secondary. I picked Track 02 only, as asked. Add the others only if you can defend them.)

### Two reasons from the repo
1. **Memory is the thing being tested, and we measured it.** The graph keeps "remembered normal" nodes stored as of each time T, and every detector reads only at or before T (core/graph/as_of.py; core/normal/metrics.py). In the memory ablation on 100 planted campaigns, full memory detects 0.88; remembering only the last 90 days gives 0.82; the last 30 days gives 0.60. On a clean set of 20, full memory flagged 1; both forgetful versions flagged all 20 (eval/results/ablation_memory.json).
2. **Agents coordinate through a task board in the graph.** Workers claim tasks with leases, stale results are rejected, and notes are unique per finding (core/board/board.py). The race test ran 8 workers on 200 tasks with 0 duplicate claims and 40 notes for 40 findings; five different task orderings gave identical findings (eval/results/race_run.json; eval/results/determinism_run.json).

## Links
- Public repo: `<<https://github.com/YOUR-NAME/hearthguard>>`
- Demo video: `<<video link>>`
- Live demo / deployment: `<<https://YOUR-NAME.github.io/hearthguard/>>` (a static offline copy of the saved results; the full system runs locally)
- Blog post (side prize): `<<dev.to or Hashnode link>>`

## Setup instructions (paste)
Full steps are in the README under "Setup". Short version: install `uv`, Docker (and Node for the UI); run `uv sync`; create `.env` with `HEARTHGUARD_HASH_SALT=<any long random text>`; run `docker compose up -d` (image pinned to `falkordb/falkordb:6.0.2`). The demo needs no key and no database: `uv run python -m eval.demo`. No API key is needed for any judge step.

## Graph data model (paste)
One graph per organisation, `org_<id>`: Org, Actor (hashed id), Action (commit, review, issue, release), Path, Privilege, with edges DID, VIA, GRANTED, CAN_GRANT, APPROVED. Remembered-normal `Normal` nodes are stored as of time T. A claim graph links Source, Span and Claim. Agents use Finding, Note, Task, AgentStep and Hardening nodes. A separate `ecosystem_<id>` graph holds Place, Identity, Role, Signal and Decision. Scratch graphs (`redteam_<run>`, `harden_<run>`) are copies made with GRAPH.COPY. Details: README "Graph data model".

## Cypher queries and algorithms the product depends on (paste)
`algo.SPpaths` for takeover cost and the trust path; `algo.maxFlow` (one relationship type) for guardians; time-filtered reads through `GRAPH.RO_QUERY` with explicit timeouts. Every Cypher constant is in docs/queries.md, generated from the code.

## How FalkorDB is used (Rules 2 and 3)
Every detector, memory read, trust path, takeover cost, visibility gap and hardening replay runs as a query on FalkorDB. The task board is also in the graph. Integration tests use a real FalkorDB container, not mocks. Honest note: the static demo page reads saved result files, so the demo page alone does not prove this; the tests and the commands in the README do.

## Data (Rule 6)
Public, synthetic or our own data only. Real data: the public xz git history and public xz-devel mailing-list posts. Synthetic: the "tallowdate" case and the "Northbridge" finance case, labelled `synthetic: true`. Identifiers are hashed on ingest. No per-project public output.

## AI assistance (Rules 11 to 13) (paste)
Claude Code (an AI coding assistant) wrote most of the code and tests under the owner's direction. Every AI-assisted step is logged in docs/AI_USE.md. A Haiku 5.5 subagent gave a blind second opinion on test-set labels, marked as an AI opinion. The Reader calls `openai/gpt-oss-20b` through Groq for claim extraction only; no other product code calls a model. `<<OWNER: add one or two sentences, in your own words, on what you decided and can explain, e.g. the graph model and one detector. Rules 12 and 13 need a human who can explain the project. No module has a named owner in the repo yet.>>`

## Honest note about commit dates (paste, edit if needed)
"I began thinking through the Hearthguard idea and setting up its basic structure before the hackathon opened. I researched how slow supply-chain takeovers like the xz case happen, chose the data sources, and wrote the first specification and project skeleton on October 12 and 13. I am stating this openly so the judges can see exactly what existed before the start and what was built during the event."

Commits per day, from `git log` on branch coding/s4-submission (merge commits are counted in the commit column but add no files; the folder counts come from non-merge commits; "files touched" counts a file once per commit):

| Date (2026) | Commits | Main folders changed (files touched) |
|---|---|---|
| Oct 12 | 115 | eval (155), docs (75), core (55), ui (46), redteam (23) |
| Oct 13 | 12 | eval (51), core (17), docs (4), ui (3), redteam (2) |
| Oct 15 | 12 | eval (39), demo (25), docs (8), ui (5), core (1) |
| Oct 17 | 21 | ui (33), eval (28), demo (16), docs (9), core (1) |
| Oct 18 | 1 | docs (9), eval (3) |

OWNER TO CONFIRM: which parts above were built after Oct 15 12:01 AM IST.

## Honest limits (paste)
No public grant record exists for real xz, so takeover cost, Rush, Bypass and Lone keeper are NOT COMPUTED on it and the decision is HOLD in all 10 quarters. The xz backdoor was in release tarballs, not git; this build does not detect it. The Reader read 94 of 240 messages and its precision and recall are NOT COMPUTED (no human labels). The Act II case is synthetic and labelled. The Slack send path is tested with a fake sender; no real Slack message was sent. There is no live deployment beyond a static demo page.

## Team
`<<names and GitHub handles of members>>` (solo or up to 4; each person on one team only).

## Contact email
`<<your email>>`
