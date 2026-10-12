# Blog outline (draft)

Working title, from the spec: "He was alone. She wasn't: building a memory for slow attacks" (docs/HEARTHGUARD.md §20). Every fact below comes from a file in this repo. Act II is synthetic wherever it appears.

## 1. The problem: slow attacks

Public history can hide who held release rights, because the git log does not record grants (eval/results/xz_grant_search.json).

## 2. What git history cannot show

The xz backdoor was in the release tarballs, not in the git history, so a git-only replay cannot show it (eval/results/xz_normal.json, notes).

## 3. What we built

Hearthguard keeps a graph of who could change a project, in FalkorDB (docs/HEARTHGUARD.md §5).

## 4. How the replay works

The replay covers 10 quarter-ends, from 2021-Q4 to 2024-Q1, and reads saved files only (eval/results/decision_status.json; eval/results/build_report.md).

## 5. The four moves, and why each can look harmless alone

Pressure, Vouch, Rush and Bypass are the four moves in the spec (docs/HEARTHGUARD.md §7.1); in this build, Pressure and Vouch ran and Rush and Bypass did not compute (eval/results/decision_status.json).

## 6. What the replay found

Every quarter is HOLD, because two moves cannot be computed (eval/results/decision_status.json).

## 7. Why takeover cost is NOT COMPUTED

No grant record exists in the public data we searched, so takeover cost has no input (eval/results/xz_grant_search.json; eval/results/xz_takeover_status.json).

## 8. The Reader, and how far it got

The model's free daily allowance stopped the Reader after 94 of 240 messages (eval/results/reader_full_progress.json).

## 9. What we could not measure

The Reader's precision and recall are NOT COMPUTED, because no human labels exist yet (eval/results/build_report.md).

## 10. Frozen rules, and what is not frozen

The thresholds come from the spec (config/frozen.yaml), and the freeze document is still a draft (eval/results/build_report.md, item 3; eval/results/completion_full.md, row 77).

## 11. Tests and repeatable output

The test suite recorded 467 passed and 1 xfailed, and the demo prints the same bytes each run (eval/results/final_tests.json; eval/results/build_report.md).

## 12. The Act II case, synthetic

The `tallowdate` case is synthetic and not built yet (docs/HEARTHGUARD.md §3.5; eval/results/completion_full.md, row 16).

## 13. Ethics by design

Identifiers are hashed on ingest, and only public or synthetic data is used (eval/results/completion_full.md, row 2; docs/HEARTHGUARD.md §4.5).

## 14. How AI was used

Claude Code wrote most of the code, and each step is logged (docs/AI_USE.md).

## 15. Where it stands

20 of 131 planned rows are DONE, and the project is not complete (eval/results/completion_full.md).

## 16. What comes next

The next steps are the NOT STARTED rows, starting with grant data and human labels (eval/results/completion_full.md; docs/submission_checklist.md).
