# Blockers for setup, README and writeup rows

Rows in eval/results/completion_full.md that need a person, so this branch does not attempt them. Written 2026-10-17 on branch coding/setup-docs.

| Row | Item | Status in completion_full.md | Reason it is blocked |
|---|---|---|---|
| 129 | Pitch: demo video, 3 minutes (spec §14) | NOT STARTED | A person must record and upload the video. docs/video/shot_list.md and narration.md are a script only; no video file exists in the repo. eval/video_check.py can check the numbers once a video exists. |
| 130 | Pitch: blog post (spec §20) | PARTIAL | The post is written and checked against its files (docs/blog/post.md). Publishing it on a public site needs a person: the account, the platform and the final read are theirs to choose. Not published here. |
| 131 | Pitch: submission form and track mapping (spec §19) | NOT STARTED | A person must fill in the submission form on the event site. The track name (Track 02, Agent Memory and Coordination) is in docs/submission_checklist.md and was not re-checked against the event page. |

Not blocked, and handled in this branch: row 6 (clean-clone setup), row 128 (README). Their evidence is in docs/fresh_clone_report.md (run 8).
