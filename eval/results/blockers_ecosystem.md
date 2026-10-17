# Blockers: open ecosystem and evidence rows (coding/ecosystem-evidence)

Each open row in `eval/results/completion_full.md` that is about the ecosystem graph, who-saw-what,
the evidence trail, takeover cost, guardians, hardening, the patience curve, the replay, the trust
map or the playbook, or that uses only cached data. Every reason names the saved file or the
blocker note it comes from. Nothing here is computed by hand, and no row was marked DONE by hand.

Checked before any change: commit 2c0b48f (block G ingest, ecosystem work) and commit b09068e
(Org and Campaign nodes in `ecosystem_xz`, `eval/results/blockers_40.md`) are present, and
`packs/oss/ecosystem/graph.py` writes Org (2) and Campaign (1) as `eval/results/ecosystem_load.json` shows.

## Done in this run (still PARTIAL, not marked DONE)

- **Row 35** Place, PARTICIPATES_IN, RECORDED_IN. The git part was skipped in the earlier run because
  `HEARTHGUARD_HASH_SALT` was not set. It is now set, and the run was made:
  `uv run python -m eval.populate_visibility --git --out eval/results/visibility_xz_git.json`.
  Result: 4,509 commits read; 96 PARTICIPATES_IN actors; 323 RECORDED_IN; second run identical.
  The 323 RECORDED_IN are the mail messages only. Commits are linked to a place only when their
  Action already exists in the graph, and `org_xz_visibility` is a fresh graph with no commit
  Actions. Linking commits needs the Actions written into `org_xz`, the real graph, which this run does not change.
  The saved mail-only result `eval/results/visibility_xz.json` is unchanged.
- **Row 74** who-saw-what. PARTICIPATES_IN is now filled from the cached mail and git data (same
  file, 96 actors). WATCHES is not written; see row 74 below.

## Open rows: data does not exist, or a decision is needed

| Row | Item | Status | Reason |
|---|---|---|---|
| 11 | Takeover cost on real xz over time | NOT STARTED | NOT COMPUTED, reason "no CAN_GRANT or Privilege data in org_xz (git history has no grant record)". `eval/results/xz_takeover_status.json`; grant search `eval/results/xz_grants_unknown.json`. |
| 13 | Outsider edge rule settled | PARTIAL | Needs the owner's decision. `docs/decisions/0001-outsider-edges.md` is PROPOSED. Not a data gap. |
| 17 | Core free of domain code | PARTIAL | `core/normal/metrics.py` and `core/detectors/bypass.py` still hold OSS words. Moving them changes code outside this run's rules (detectors). `eval/results/blockers_H.md` row 17. |
| 24 | Foundation view across projects (Could) | NOT STARTED | No cached record names a foundation (grep of `data/raw` for "foundation" finds nothing). `eval/results/blockers_40.md`. |
| 34 | Privilege, GRANTED, CAN_GRANT, APPROVED | PARTIAL | No documented grant record exists for xz. `eval/results/xz_grants_unknown.json`. The mapping (`packs/oss/grants.py`) is built; there is no input. |
| 36 | SHARES edges | NOT STARTED | `creation_window` needs account creation dates, which the public record does not hold; `domain_hash` over mail domains mostly matches public providers. `docs/decisions/0004-mail-claims-in-org-xz.md` point 4. |
| 37 | CONTRADICTS / SUPERSEDES / QUALIFIES pairs | PARTIAL | Pairs are supplied by the caller; no detector finds them. Reader claims have an empty `Claim.target_hid` (decision 0004 point 3). Pair detection is not specified by a frozen rule. |
| 38 | Objection and Request writers | PARTIAL | No Skeptic source; nothing calls the writers. `eval/results/blockers_a.md` row 38. |
| 40 | ecosystem_<id> graph | PARTIAL | Foundation and HOSTED_BY: no public source in the cache. Campaign `status`: no public source. Org and Campaign are written (see above), so the row's text "Campaign not written" is out of date, but the row stays PARTIAL. `eval/results/blockers_40.md`. |
| 42 | census_<date> graph | NOT STARTED | No census data. `eval/results/blockers_census.md`. |
| 43 | playbook: compiled investigation plans | PARTIAL | Plans need an LLM call or a deterministic template; neither exists. `eval/results/blockers_E.md` row 43. |
| 46 | Pressure detector | PARTIAL | Keeper condition OPEN, `docs/decisions/0005-pressure-keeper-activity-open.md`. Detector not changed. |
| 47 | Vouch detector | PARTIAL | No target and no SHARES (decision 0004). Detector not changed. |
| 50 | Lone keeper multiplier | PARTIAL | Rule PROPOSED, decision 0001. Detector not changed. |
| 51 | Detectors give a computed result on real xz | NOT STARTED | `eval/results/xz_detector_status.json`: Rush NOT_COMPUTED (no `release` Privilege, so no grant data); Bypass NOT_COMPUTED (single shared Path node, no variation). |
| 55 | Trust path on real data | PARTIAL | `eval/trust_path_tallowdate.py` is hard-wired to the synthetic tallowdate actors. xz has no grant to trace to, so there is no path result. `eval/results/xz_takeover_status.json` records the reason. |
| 59 | Watcher worker | PARTIAL | No worker process, no SHARES. |
| 62 | Skeptic | NOT STARTED | The benign-explanation search is an LLM step; no Skeptic code exists. `docs/decisions/0008-inbox-no-llm.md`. |
| 66 | Learned exceptions with regression gate | PARTIAL | Adopted does not act; needs per-actor move evidence. `eval/results/blockers_E.md` row 66. |
| 68 | Compiled plans | NOT STARTED | LLM plan step; none built. `eval/results/blockers_E.md` row 43. |
| 73 | Procedural: remembered normal | PARTIAL | 3 of 6 metrics COMPUTED (`eval/results/xz_normal.json`: cadence_days, active_keepers, usual_path). `keeper_activity_median_90d` depends on the open Pressure condition (decision 0005). `grant_days` and `trusted_actor_set` need grant data, which does not exist. |
| 74 | WATCHES {since} | PARTIAL | See the note below the table. |
| 80 | Learning proof, targets and seeds | PARTIAL | `make verify-learning` and `make chaos` targets are not wired; seeds 1-4 give the same exception. `eval/results/blockers_E.md` row 80. |
| 83 | xz replay | PARTIAL | `eval/replay_xz.py` runs; no detector fires and 146 messages are unread (the Reader is an LLM step, not run here). |
| 85 | Hardening on xz and 10 false-alarm projects | PARTIAL | The xz half is done. The 10 false-alarm projects are not in the repo and are not invented. |
| 86 | Ownership accuracy, about 30 projects | NOT STARTED | No cached set of about 30 projects. Fetching one is a new network ingest, outside this run's rules. |
| 88 | Takeover Cost Census (`make census N=100`) | NOT STARTED | No census registry records cached. `eval/results/blockers_census.md`. |
| 89 | False-alarm study, about 30 projects | NOT STARTED | No cached projects set. `make false-positives` is not built (`eval/results/blockers_I.md`). |
| 90 | Reader eval, about 100 hand-labelled spans | PARTIAL | No human labels exist. Labels must not be invented. `eval/results/reader_labelsheet.csv` is unlabelled. |
| 94 | Finance case: Pressure, Vouch, Liaison note | PARTIAL | Pressure and Vouch need claims from the Reader (an LLM step). `eval/results/blockers_H.md` row 94. |
| 95 | Takeover Cost Census ingest (npm) | NOT STARTED | No npm registry records for N public packages are cached. `eval/results/blockers_census.md`. |
| 119 | Census screen | PARTIAL | Screen exists; `eval/results/census.json` is absent, so it shows NOT COMPUTED. `eval/results/blockers_census.md`. |
| 124 | Discord and email front ends (Could) | NOT STARTED | No accounts or tokens are configured for either service. |
| 125 | Vector search for similar pressure messages (Could) | NOT STARTED | `sentence_transformers` is not installed, so no Span is embedded. `eval/results/blockers_H.md` row 45. |
| 126 | Non-English pressure detection (Could) | NOT STARTED | No non-English record set is cached or specified. |
| 127 | Three real-maintainer reactions, with consent | NOT STARTED | Human input. Nothing may be invented. |

### Row 74, WATCHES
`eval/results/ecosystem_events.json` has 3 events with role `xz upstream maintainer` (2 in
`xz-git`, 1 in `lkml`) and 3 with role `committer` in `xz-git`. A WATCHES edge for an xz role
could therefore be drawn from cached records. It is not written: the ecosystem model (`packs/oss/ecosystem/graph.py`)
writes WATCHES only for the roles of its four decision records, and no xz decision record exists.
Choosing which xz roles count as watching is a modelling choice for the owner. Until it is made,
who-saw-what for xz holds PARTICIPATES_IN only.

## Rows not touched: outside this run's scope or rules

- Inbox, Slack, safety, Liaison, owner memory, slash commands, Investigator: rows 22, 61, 63, 75, 100, 102, 104, 108, 109, 29 (notes part).
- Setup, clone, public repo, README, writeup, video, blog, submission, tracks: rows 3, 6, 9, 128, 129, 130, 131.
- Freeze files (`docs/FREEZE.md`, `docs/FREEZE.sha256`): row 77. Not edited, per the run rules.
- MCP client configuration and the Claude Code `check_trust` demo: rows 26 and 99. `eval/results/blockers_I.md` says no client config or demo script was written. Treated as setup, not run.
- Row 8 (named module owners) and row 29 (ethics, notes and census) need human input or belong to the inbox/census rows.
