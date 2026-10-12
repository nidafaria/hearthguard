# Facts for the blog post

Each line: the fact, then its source file and field. Read from the files at commit 00b09ea on main, 2026-10-12. Files under `data/raw/` are git-ignored and exist only in the main checkout.

## Build status

- The build report is dated 2026-10-12. Source: `eval/results/build_report.md` (line 3).
- Tests: 467 passed, 0 failed, 1 xfailed. Source: `eval/results/build_report.md` (line 21, "Acceptance output"), and `eval/results/final_tests.json`.
- Every number in the build report comes from a saved file named beside it. Source: `eval/results/build_report.md` (line 3).
- The Reader step (Step C) is incomplete. The daily limit of 200,000 tokens stopped the run at 94 of 240 messages. Source: `eval/results/build_report.md` (line 29, "Differences from the spec", item 1), and `eval/results/reader_full_progress.json`.
- The next unread message is msg00507, with 146 remaining. Source: `eval/results/build_report.md` (line 29), and `eval/results/reader_full_run.json` field `remaining` (146).
- The 60 test-set messages are deliberately not read. They are for human labels. Source: `eval/results/build_report.md` (line 29), and `eval/results/reader_full_run.json` field `excluded`.
- The Reader was not scored against human labels. Reader precision and recall are NOT COMPUTED, for "no human labels". Source: `eval/results/build_report.md` (line 52, "NOT COMPUTED").
- Reader frozen version is 1. Source: `eval/results/reader_full_run.json` field `reader_frozen_version` (1).
- Reader model name recorded in the run: openai/gpt-oss-20b. Source: `eval/results/reader_full_run.json` field `model`.

## Reader run (94 messages)

- The run covers 240 messages in scope. Source: `eval/results/reader_full_run.json` field `messages_in_scope_total` (240).
- Messages done: 94. Source: `eval/results/reader_full_run.json` field `messages_done` (94).
- Claims extracted: 3, all of kind CAPACITY_STATEMENT. Source: `eval/results/reader_full_run.json` fields `totals.claims` (3) and `totals.claims_by_kind`.
- Quotes rejected: 6, all for "quote is not a substring of the message text". Source: `eval/results/reader_full_run.json` field `totals.rejections_by_reason`.
- Messages with no claim: 91. Source: `eval/results/reader_full_run.json` field `totals.messages_without_claims` (91).
- Messages not read because they were too long for one request under the 8,000 tokens-a-minute limit: 4. Source: `eval/results/reader_full_run.json` field `totals.messages_not_read_too_long` (4), and `eval/results/build_report.md` (line 30).
- Messages with invalid JSON output: 0. Source: `eval/results/reader_full_run.json` field `totals.messages_not_read_no_valid_json` (0).
- Token totals for the run: input 110,366; output 44,479; reasoning 42,803. Source: `eval/results/reader_full_run.json` field `totals`.
- Fresh model calls: 81. Cache hits: 9. Source: `eval/results/reader_full_run.json` fields `totals.fresh_calls` and `totals.cache_hits`.
- The Reader's three claims are CAPACITY_STATEMENT. The build report says Pressure and Vouch did not fire because the Reader returned no PRESSURE, URGENCY or VOUCH claim, and its recall is not measured. Source: `eval/results/build_report.md` (line 44).

## Detectors on the public xz history

- Action used for the check: release v5.6.1. T is 2024-03-31T23:59:59Z. Source: `eval/results/xz_detector_status.json` fields `action_ref`, `T_iso`.
- Rush: NOT_COMPUTED. Reason: no Privilege of kind 'release' in org_xz, so no grant data. Source: `eval/results/xz_detector_status.json` field `detectors.rush`.
- Bypass: NOT_COMPUTED. Reason: a single shared Path node, so no variation to compare. Source: `eval/results/xz_detector_status.json` field `detectors.bypass.reason`.
- Lone keeper: NOT_COMPUTED. Reason: guardians not computed, no CAN_GRANT or Privilege data. Source: `eval/results/xz_detector_status.json` field `detectors.lone_keeper.reason`.
- The file's note says the real xz history has no grant data and one shared release path, and the detectors are tested on hand-built graphs in tests/fixtures/detector_cases.py. Source: `eval/results/xz_detector_status.json` field `note`.
- Grant records found: 0, in 14 sources. Source: `eval/results/build_report.md` (line 40), and `eval/results/xz_grant_search.json`.
- Pressure and Vouch: NOT_FIRED in all 10 quarters, on the messages read only. Source: `eval/results/build_report.md` (line 42).
- Pressure computes only the claim condition. The keeper condition is open (decision 0005). Source: `eval/results/build_report.md` (line 33, item 5).
- Decision: HOLD in all 10 quarters, reason "move unknown: RUSH, BYPASS". Source: `eval/results/build_report.md` (line 43).
- The takeover cost is NOT COMPUTED. Reason: no CAN_GRANT or Privilege data in org_xz. Source: `eval/results/xz_hardening.json` field `results[0].steps[0].before.takeover_cost`.

## Normal metrics over 10 quarter-ends (public git history only)

- Source of the metrics: the xz git repository at https://git.tukaani.org/xz.git, head SHA 3b1efb04d17c3a9ef7f473d73af13f1531428ffe, fetched 2026-10-12T08:12:21Z. Source: `eval/results/xz_normal.json` field `source`.
- The file says the xz backdoor was in release tarballs, not in the git history, so these numbers do not show the backdoor. Source: `eval/results/xz_normal.json` field `notes` (item 1).
- The file says active_keepers counts distinct commit authors, which can overcount keepers. Source: `eval/results/xz_normal.json` field `notes` (item 2).
- The file says usual_path is always git here, because git is the only channel the ingest can see. Source: `eval/results/xz_normal.json` field `notes` (item 3).
- There are 10 quarter-ends, from 2021-Q4 to 2024-Q1. Source: `eval/results/xz_normal.json` field `results`.
- active_keepers by quarter, from 2021-Q4 to 2024-Q1: 4, 3, 3, 3, 2, 2, 5, 7, 5, 7. Source: `eval/results/xz_normal.json` field `results[*].metrics[active_keepers].value`.
- cadence_days (median gap between commits, in days) by quarter: 0.00523, 0.00907, 0.01858, 0.01407, 0.01439, 0.00551, 0.00494, 0.00403, 0.00477, 0.00382. Source: `eval/results/xz_normal.json` field `results[*].metrics[cadence_days].value`.
- Commit gaps counted for cadence_days: 201 at 2021-Q4, rising to 1584 at 2024-Q1. Source: `eval/results/xz_normal.json` field `results[*].metrics[cadence_days].n`.
- Releases in the 730-day window, all via git: 2, 1, 1, 4, 10, 14, 16, 17, 17, 22 by quarter. Source: `eval/results/xz_normal.json` field `results[*].metrics[usual_path].n`.
- keeper_activity_median_90d: NOT COMPUTED in every quarter. Reason: it depends on the open Pressure keeper-activity condition (spec §7.6). Source: `eval/results/xz_normal.json` field `results[*].metrics[keeper_activity_median_90d].reason`.
- grant_days and trusted_actor_set: NOT COMPUTED in every quarter. Reason: git records no grants. Source: `eval/results/xz_normal.json` fields `results[*].metrics[grant_days].reason` and `trusted_actor_set.reason`, and `eval/results/xz_grants_unknown.json`.

## Hardening simulator on the same history

- The file's red_team field says "not run: caught and lead time are not in this file". Source: `eval/results/xz_hardening.json` field `red_team`.
- The rule tested is 0001-outsider-edges, which is PROPOSED. Source: `eval/results/xz_hardening.json` field `rule`.
- Org graph before and after: 4679 nodes and 4668 edges, unchanged. Source: `eval/results/xz_hardening.json` fields `org_counts_before`, `org_counts_after`.
- There are 10 quarter-ends in the simulation. Source: `eval/results/xz_hardening.json` field `results`.
- Step require_provenance_ci: applied in all 10 quarters, set 10 properties in each. Source: `eval/results/xz_hardening.json` field `results[*].steps[require_provenance_ci].graph_changes`.
- Step add_second_keeper: not applied in any quarter, because there was no Privilege, grant edge or usual_path Normal to act on. Source: `eval/results/xz_hardening.json` field `results[*].steps[add_second_keeper].applied` and `note`.
- Step require_two_approvals: not applied in any quarter, for the same reason. Source: `eval/results/xz_hardening.json` field `results[*].steps[require_two_approvals].applied`.
- Takeover cost before and after every step: NOT COMPUTED. Reason: no CAN_GRANT or Privilege data in org_xz. Source: `eval/results/xz_hardening.json` field `results[*].steps[*].before.takeover_cost`.

## Completion (self-assessment)

- Total rows in the completion table: 131. Source: `eval/results/completion_full.json` field `total_rows`.
- DONE 21, PARTIAL 36, NOT_STARTED 74. Source: `eval/results/completion_full.json` fields `DONE`, `PARTIAL`, `NOT_STARTED`.
- Score: 29.8 percent, with DONE weighted 1 and PARTIAL weighted 0.5. Source: `eval/results/completion_full.json` fields `score_percent`, `weights`.
- The earlier score was 24.8 percent, measured at commit 8955f72, before the four branches were merged. Source: `eval/results/completion_full.json` field `previous`.
- The rows come from docs/HEARTHGUARD.md and the pitch deliverables, in eval/completion_full.py. Source: `eval/results/completion_full.json` field `source`.

## The xz maintainer's public words

- Message msg00563 on the xz-devel list, by Lasse Collin, dated 19 May 2022. Source: `data/raw/mail/xz-devel/msg00563.html` (span class "date" and "sender").
- The public sentence: "It's clear that my resources are too limited". Source: `data/raw/mail/xz-devel/msg00563.html` (article body, line 102).
- The file eval/results/video_quotes.json does not exist. The quote therefore comes from the cached message. Source: directory check of `eval/results/` at commit 00b09ea.
- The spec says to quote only these public words, respectfully, and never speculate beyond them. Source: `docs/HEARTHGUARD.md` line 134.

## Synthetic story and data rules

- Act II of the demo is the synthetic tallowdate story. Source: `docs/HEARTHGUARD.md` §22 (glossary, row "Act I / Act II").
- The tallowdate outputs are not cited in this post. Source: `eval/results/` file list (tallowdate_*.json exist and are not used here).
- Every synthetic entity carries `synthetic: true`. Source: `CLAUDE.md` section "Data and privacy".
- Planted entities carry `planted: true` and a `campaign_id`. Detectors must never read these flags; only the scorer does. Source: `CLAUDE.md` section "Data and privacy".
- Identifiers are hashed on ingest. Source: `CLAUDE.md` section "Data and privacy" (spec §1 R6).
- No public per-project output. Source: `CLAUDE.md` section "Data and privacy".
- The LLM is never in the decision path. Detectors, the conflict policy, the decision policy, takeover cost, guardians, gaps and hardening are deterministic code. Source: `CLAUDE.md` section "The LLM is never in the decision path" (spec §8.4).
- Section 20 of the spec sets the post structure. Source: `docs/HEARTHGUARD.md` §20.
- Census: no census output file exists in eval/results/ at this commit. Source: directory check of `eval/results/` at commit 00b09ea.
- The hardening simulator's red-team replay was not run. Source: `eval/results/xz_hardening.json` field `red_team`.
