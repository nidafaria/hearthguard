# Numbers to quote

Every number below was read from the saved file named beside it (read on 2026-10-18 in the branch `coding/s4-submission`). Quote only what is in this table. If a number is not here, do not say it.

Where two files disagree, the row says so in the last column.

| # | Number | Value | Source file (field) | Used in | Disagreement |
|---|---|---|---|---|---|
| 1 | Actions in the public xz git graph | 4,569 | eval/results/xz_ingest.json (counts_after_run_1.nodes.Action) | video, blog | no |
| 2 | Git actors (hashed authors) | 68 | eval/results/xz_ingest.json (counts_after_run_1.nodes.Actor) | video | **Yes, in a different graph.** eval/results/build_report.md says 69 actors in `org_xz` after the Reader wrote claims (1 is mail-only). eval/results/visibility_xz_org.json says 96 actors on a copy that adds mail posters. Say "68 git author identities" and nothing else. |
| 3 | xz git head used | 3b1efb04 (fetched 2026-10-12) | eval/results/xz_ingest.json (head_sha, fetched_at_utc) | blog | no |
| 4 | Active commit authors per quarter-end, 2021-Q4 to 2024-Q1 | 4, 3, 3, 3, 2, 2, 5, 7, 5, 7 | eval/results/xz_normal.json (active_keepers) | blog | no |
| 5 | Median gap between commits | 0.00523 days (2021-Q4); peak 0.01858 (2022-Q2); 0.00382 (2024-Q1) | eval/results/xz_normal.json (cadence_days) | blog | no |
| 6 | Releases in 730-day window | 2 (2021-Q4) to 22 (2024-Q1) | eval/results/xz_normal.json (usual_path n) | blog | no |
| 7 | Grant records found for real xz | 0, from 14 sources | eval/results/xz_grant_search.json (grant_records_found, sources) | video, blog, form | no |
| 8 | Takeover cost on real xz | NOT COMPUTED (say it that way; never a number) | eval/results/xz_takeover_status.json | video, blog, form | no |
| 9 | Decision per quarter on xz | HOLD in all 10 quarters, "move unknown: RUSH, BYPASS" | eval/results/decision_status.json | video, blog, form | no |
| 10 | Reader messages done / in scope / left | 94 / 240 / 146 | eval/results/reader_full_progress.json (done, total, remaining) | video, blog, form | no |
| 11 | Reader stop reason | daily limit of 200,000 tokens on openai/gpt-oss-20b | eval/results/reader_full_progress.json (stopped_because) | blog | no |
| 12 | Reader: claims, rejected quotes, no-claim messages, too long | 3 (all CAPACITY_STATEMENT), 6, 91, 4 | eval/results/reader_full_run.json (totals) | video, blog | no |
| 13 | Reader tokens | 110,366 in, 44,479 out, 42,803 reasoning | eval/results/reader_full_run.json (totals) | blog | no |
| 14 | Reader precision and recall | NOT COMPUTED (no human labels yet) | eval/results/reader_testset.json; labels file is empty | video, blog, form | no |
| 15 | Hardening on copy of xz history (quarters) | 10 quarter-ends; require_provenance_ci set 10 properties in the first quarter; 4,679 nodes and 4,668 edges | eval/results/xz_hardening.json | blog | **Near-miss.** eval/results/hardening_redteam_xz.json shows 11 properties for the same step. That is a different run (planted campaigns). Do not mix them. |
| 16 | Red-team on synthetic tallowdate, 200 campaigns | 182 caught, detection 0.91, median lead 12.8 days | eval/results/redteam_tallowdate.json (summary) | form, video (optional) | no |
| 17 | Red-team planted into copy of xz history, 200 campaigns | 167 caught, detection 0.835, median lead 11.0 days | eval/results/redteam_xz.json (summary) | form, blog | no |
| 18 | Hardening: add a second keeper | guardians 1 to 2; caught 167 to 152 of 200 (0.835 to 0.76); build does not explain the drop | eval/results/hardening_redteam_xz.json (steps) | blog, form | no |
| 19 | Memory ablation, 100 campaigns | detection 0.88 full, 0.82 last 90 days, 0.60 last 30 days. Clean set (20): flagged 1 with full memory, 20 with either forgetful memory | eval/results/ablation_memory.json (arms) | form, video (optional) | no |
| 20 | Race test | 8 workers, 200 tasks, 0 duplicate claims, 40 notes for 40 findings | eval/results/race_run.json | form | no |
| 21 | Determinism | identical findings under 5 task orderings | eval/results/determinism_run.json | form | no |
| 22 | event-stream replay (2018) | first NOTE 2018-09-16, 7.1 days after the malicious release (2018-09-09) and 64.1 days before the public report (2018-11-19) | eval/results/replay_event_stream.json (replay.points, malicious_release_utc, public_report_utc). The two day counts are my subtraction from those dates; they are not stored fields. | blog (optional) | no |
| 23 | axios replay (2026) | Bypass did not fire: 33 of 37 releases were manual publishes | eval/results/replay_axios.json (text) | form (optional) | no |
| 24 | Visibility gaps on xz | 4 decisions computed, 22 gap rows (21 UNREACHABLE, 1 UNNOTICED), a lower bound | eval/results/ecosystem_gaps.json | form (optional) | no |
| 25 | Synthetic tallowdate: accounts created | 2026-02-10, 2026-02-11, 2026-02-12 | eval/results/tallowdate_demo_script.json | video | no |
| 26 | Synthetic tallowdate: reviewer's reviews | 140 | eval/results/tallowdate_load.json (facts.tomas_review_count) | video | no |
| 27 | Tests passed | 467 passed, 0 failed, 1 xfailed (run 2026-10-12 at commit 796ac40) | eval/results/final_tests.json | video | **Yes.** README.md (line 70) and docs/fresh_clone_report.md (line 199) say 959 passed, 0 failed, 1 xfailed on main. There is no JSON for 959. The 467 file is from Oct 12; many commits came after it. Before you quote either, re-run `uv run pytest` yourself on a free port and use what you see. Until then the safe sentence is "the saved test result file says 467 passed (Oct 12); the README says 959 on the final main". |
| 28 | Project completion | 75 DONE, 35 PARTIAL, 21 NOT STARTED of 131; score 70.6% | eval/results/completion_full.md (line 3) | blog, form | **Yes (fixed in blog_final.md).** docs/blog/post.md said 69.1% with 72/37/22. That is the older number. |
| 29 | Real-xz public places with traces ("six") | NOT COMPUTED; do not say "six" | eval/results/video_numbers.json (SIX_PUBLIC_PLACES) | none | no |
| 30 | Connect-a-repo timing | 3.045 s wall clock, repo octocat/Hello-World (3 commits) | eval/results/connect_repo_run.json | form (optional) | no |
| 31 | Slack sends | sent_to_slack false; the send path is tested with a fake sender only | eval/results/slack_preview.json; eval/results/blockers_slack_sender.md | video, form | no |
| 32 | Commits: before and after the start | 127 commits before Oct 15 12:01 AM IST (115 on Oct 12, 12 on Oct 13); 33 on or after (12 on Oct 15, 21 on Oct 17); 160 in all. First commit 2026-10-12 13:21 IST | `git log --format=%ad` on main at c77c823 | form | no |
| 33 | Deadline | 11:59 PM IST, Sunday Oct 18, 2026 | https://www.wemakedevs.org/hackathons/falkordb/rules (Rule 7) | checklist | **Yes.** docs/submission_checklist.md says "about 6:00 PM IST". The rules page says 11:59 PM IST. Use the rules page. |

## Not to say (no saved result)

- A takeover cost for real xz. A Reader precision or recall. A count of "six public places". Anything about the backdoor being found by the tool: the README says it does not detect it.
- Any reaction from a maintainer. There are none on file (see docs/submission/replies.md).

## Changes made to the blog in blog_final.md

Compared with docs/blog/post.md (the original is untouched):
1. Completion line: 69.1% (72 DONE, 37 PARTIAL, 22 NOT STARTED) changed to 70.6% (75, 35, 21), from eval/results/completion_full.md line 3.
2. Removed three sentences to bring the word count from 1,624 back under the 1,600 limit that eval/blog_check.py enforces (now 1,593; checker passes, 106 numbers each with a source).
3. "The repository has no remote" reworded so it stays true after you push.
All other numbers in the post were checked against the saved files and match (keepers, cadence, release counts, hardening node and edge counts, Reader totals, 167 to 152, 14 sources, 0 records).
