# Blockers: open rows (branch coding/open-rows)

Every row of `eval/results/completion_full.md` that is still PARTIAL or NOT STARTED after this
branch, with the reason it is blocked. Reasons come from the earlier blocker notes named in each
line; nothing here is a guess. Blocked means one of: needs a real grant record for xz (G), an owner
decision (D), an LLM step (L), a live Slack account (S), data or a network ingest that is not in
the repo (N), or a human (H).

## Finished in this branch

| Row | Result | Commit |
|---|---|---|
| 35 | DONE: xz git commits and mail linked to Place via RECORDED_IN on a copy of org_xz | 4c351cb |
| 75 | DONE: owner memory was already built and tested; the row text was stale | c33df47 |
| 26 | DONE: `check_trust` called over MCP stdio before a merge (client is a script, not Claude Code) | a5164c4 |
| 77 | still PARTIAL: `make verify-frozen` built; the file is still DRAFT | 72b385a |
| 80 | still PARTIAL: `make verify-learning` and `make chaos` wired | 48e4f46 |
| 74 | still PARTIAL: PARTICIPATES_IN now filled for xz; text updated | see git log |

## Blocked

| Row | Kind | Reason |
|---|---|---|
| 3 Public repo | H | The repo has no remote. Creating and pushing one is the owner's call; pushing was not allowed here. |
| 6 Live deployment / local setup | H | No live deployment. A clean clone still needs a database and the salt (`blockers_G.md`). |
| 8 Named module owners | D | Owners are people's names; only the team can assign them. |
| 9 Tracks named in the submission | H | The submission is not made (`blockers_setup.md`). |
| 11 Takeover cost on real xz | G | NOT COMPUTED: git has no grant record (`xz_grants_unknown.json`). |
| 13 Outsider edge rule | D | `docs/decisions/0001` is PROPOSED; the owner settles it. |
| 17 Core free of domain code | D | The remaining OSS words are in `core/normal/metrics.py` and `core/detectors/bypass.py`; the latter is a detector, which this task may not change (`blockers_H.md`). |
| 22, 100 Slack note and app | S | No workspace, token or Bolt dependency; nothing may be sent (`blockers_slack_sender.md`). |
| 24 Foundation view | N | No cached record names a foundation, and only a few cases exist, not many projects (`blockers_40.md`). |
| 25 Controller note, Mark callback | L, S | The note wording is an LLM step and the finance pack is not a web-inbox case (`blockers_inbox.md`). The callback writer is built. |
| 29 Ethics by design | S, N | Private notes need the Slack sender and the aggregate census needs census data. |
| 34 Privilege / GRANTED / CAN_GRANT / APPROVED | G | The mapping is built; no documented grant records exist for xz. |
| 36 SHARES edges | D, N | `creation_window` needs account dates and `domain_hash` needs email domains; neither is in the cache (decision 0004). |
| 37, 72 Contradiction links | D | Pair detection needs a new detector and a frozen rule; detectors may not change here. |
| 38 Objection / Request | L | No Skeptic agent; the Skeptic's search is an LLM step (`blockers_a.md`). |
| 40 ecosystem graph | N | No public source names the hosting foundation (`blockers_40.md`). |
| 42, 88, 95, 119 Census | N | No registry records for N packages are cached; fetching them is a new network ingest (`blockers_census.md`). |
| 43, 68 Compiled plans | L | A plan compiler needs the LLM or a design decision (`blockers_E.md`). |
| 45 Vector index embeddings | N | `sentence_transformers` is not a dependency and the model is not pinned (`blockers_H.md`). |
| 46, 47, 50 Pressure, Vouch, Lone keeper | D | Open or proposed rules in decisions 0001, 0004, 0005; frozen detectors may not change. |
| 51 Detectors on real xz | L, G | Partial reads: 146 messages unread by the Reader, no grant data. |
| 55 Trust path on tallowdate | G | The case records no grant, so every quarter is NOT COMPUTED. |
| 59 Watcher | D, N | Needs SHARES (row 36); the pieces exist only as scripts. |
| 61, 62, 63 Investigator, Skeptic, Liaison | L, S | LLM planner, Skeptic search and note wording; Slack sender (`blockers_a.md`, decision 0008). |
| 66 Learned exceptions | D, L | The owner must accept decision 0007; the LLM proposal is replaced by a fixed filler (`blockers_E.md`). |
| 73 Remembered normal | G | The metrics that are NOT COMPUTED carry their reasons in `xz_normal.json`. |
| 74 Who-saw-what, rest | S, N | WATCHES has no public source for xz; `already_acknowledged` before a send needs the live sender. |
| 77 Freeze protocol | H, D | The freeze and the public dated copy are the owner's; `docs/FREEZE.md` may not be edited here. |
| 80 Learning proof, rest | D | Whether "a different exception" means a different pattern is the spec owner's call. |
| 83 xz replay | L | 146 messages unread; reading them is a Reader (LLM) run. |
| 85 Hardening on 10 false-alarm projects | N | Those projects are not in the repo and are not invented. |
| 86 Ownership accuracy, 89 False-alarm study | N | About 30 projects of data that are not in the repo. |
| 90 Reader eval | H | Needs ~100 hand-labelled spans; no human labels exist. |
| 94 Finance case | L | Pressure, Vouch and the Liaison note are LLM steps (`blockers_H.md`). |
| 99 FalkorDB MCP wired read-only; Claude Code demo | H | Needs Claude Code configured on a person's machine and an external FalkorDB MCP server. `docs/mcp/claude_code_config.json` has the hearthguard-core entry. |
| 102 Simulate a fix | D | `tests/integration/test_inbox_loop.py` asserts NOT COMPUTED for xz; changing that expectation is forbidden here (`blockers_E.md`). |
| 104 It's fine button | H | The browser check against the running app is not run (`blockers_E.md`). |
| 108 Slash commands, 124 Discord/email | S | Need a live chat account. |
| 125 Vector search for pressure messages | N | Needs the embedding model (row 45). |
| 126 Non-English pressure detection | L | A Reader (LLM) step. |
| 127 Three maintainer reactions | H | Real people, with consent. |
| 128 README final, 129 Demo video | H | The video is not recorded (`blockers_setup.md`). |
| 130 Blog post | H | Publishing needs an account and a final read. |
| 131 Submission form | H | A person fills it. |

## Environment note

The first full-suite runs on the shared FalkorDB (port 6380) failed 2 to 3 tests, a different set
each run, because other sessions create and drop graphs there and two tests compare the list of
graphs before and after. All suite runs in this branch used a private container
(`hh-rows-falkordb`, `falkordb/falkordb:6.0.2`, port 6395) loaded with `make ingest-xz` and
`make normal-xz`. `make normal-xz` rewrote `eval/results/xz_normal.json`; that change was reverted.
