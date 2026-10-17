# Final submission checklist

Deadline: **11:59 PM IST, Sunday October 18, 2026** (rules page, Rule 7). The older docs/submission_checklist.md says "about 6:00 PM"; ignore that.

Status words: DONE, PARTIAL, NOT STARTED, OWNER (only the owner can do it). Status is taken from the repo on 2026-10-18 (main at c77c823). Nothing here was posted or submitted by the AI.

## A. Required by Rule 10

| # | Item | Status | Real state in the repo | What the owner does | Evidence |
|---|---|---|---|---|---|
| 1 | Public source repo | NOT STARTED (OWNER) | `git remote -v` is empty. Local only. The history scan found no key, token or salt (see github_steps.md) | Follow docs/submission/github_steps.md | eval/results/completion_full.md row 3 |
| 2 | README with setup and graph data model | DONE (with stale lines) | README.md has setup, commands, data model, queries, numbers, limits, AI use | After the push, fix the lines in section E | README.md |
| 3 | Cypher queries / algorithms | DONE | docs/queries.md is generated from the code; README lists the algorithms | Nothing | docs/queries.md |
| 4 | Demo video | NOT STARTED (OWNER) | Script and shot list only | Record using docs/submission/video_script.md; upload; put the link in README and the form | docs/video/shot_list.md |
| 5 | Live deployment or complete local setup | PARTIAL | Local setup only. `demo/index.html` is one offline page that can go on GitHub Pages | Turn on Pages from /demo (github_steps.md, part 3) and use it as the "live" link, labelled as a static demo | demo/index.html |
| 5b | Demo page opens offline | DONE | `demo/index.html` (580 KB) loads no outside file: no script, image, font, link or fetch to the web; fonts and data are inside the file. Rendered headless from file:// with no problem. The only `http` strings are the xmlns of an inline SVG and source URLs shown as text. No fix was needed | `demo/index.html` |
| 6 | Track named | PARTIAL | README names Track 02 | Choose Track 02 on the form (form_answers.md) | README.md, Tracks |

## B. Other rules

| # | Rule | Status | Real state | Evidence |
|---|---|---|---|---|
| 7 | R2/R3 FalkorDB load-bearing | DONE (a judge may push back) | Detectors, as-of reads, takeover cost, red-team and hardening run on FalkorDB 6.0.2. Some demo screens read saved JSON | core/graph; eval/results/completion_full.md row 1 |
| 8 | R6 public / synthetic data only | DONE | Ids hashed on ingest; tallowdate and Northbridge are synthetic and labelled; `data/raw/` is git-ignored | core/graph/hashing.py; .gitignore |
| 9 | R11 AI use disclosed | DONE | README "AI disclosure" and docs/AI_USE.md | docs/AI_USE.md |
| 10 | R12/R13 owner can explain each module | PARTIAL (OWNER) | Decisions 0001 to 0008 are written, all still open. No module has a named owner | docs/decisions/index.md; completion_full.md row 8 |
| 11 | Work began after the start (Rule 7) | **RISK (OWNER)** | 127 of 160 commits are dated Oct 12 and Oct 13, before the Oct 15 12:01 AM IST start. First commit 2026-10-12 13:21 IST. See form_answers.md for the honest note | `git log` |
| 12 | Spec freeze | PARTIAL | docs/FREEZE.md still says DRAFT. It said the freeze must happen before Oct 15. The hash file matches the draft | eval/results/verify_frozen.json |
| 13 | Submit by deadline | NOT STARTED (OWNER) | Nothing submitted | The form |

## C. Prize extras

| # | Item | Status | Real state | What the owner does |
|---|---|---|---|---|
| 14 | Blog post (side prize) | PARTIAL (OWNER) | docs/blog/post.md written; checked in docs/submission/blog_final.md; not published | Publish on dev.to or Hashnode; add the link to README and the form |
| 15 | Three real maintainer reactions | NOT STARTED (OWNER) | None on file. maintainer_note.md and replies.md are ready. No reply may be invented | Send the note to three maintainers if you want; log real replies only |
| 16 | Reader test set labels (60) | NOT STARTED (OWNER) | eval/labels/to_label.csv is empty | Fill the `label` column; run check_labels.py. Without labels, Reader precision and recall stay NOT COMPUTED |

## D. Weak or unfinished items (say them plainly)

- Real xz: no public grant record, so takeover cost, Rush, Bypass and Lone keeper are NOT COMPUTED. Decision is HOLD in all 10 quarters. The tool does not detect the xz backdoor (the backdoor was in tarballs, not git).
- Reader read 94 of 240 messages; precision and recall NOT COMPUTED (no human labels).
- Slack: the send path is tested with a fake sender. No real Slack message was ever sent (`sent_to_slack` false). No file in the repo shows that Window 3 changed this. Re-check before you say anything different.
- No live deployment; no census; no Skeptic agent; completion 70.6% (75 DONE, 35 PARTIAL, 21 NOT STARTED of 131).
- Test count disagrees between files (467 vs 959). See numbers.md row 27.

## E. README edits to make before you push (not done here; this task only added new files)

1. "Demo video: not recorded yet" (README line 13): replace with the video link.
2. "Deployment: local only" (line 11): add the GitHub Pages link for the static demo, if you turn it on.
3. Tracks section (line 150): the track name was checked against the rules page on 2026-10-18 and matches ("Agent Memory and Coordination"). Update "form has not been filled in yet" after you submit.
4. Test count at line 70 (959) vs eval/results/final_tests.json (467): re-run and use one number.

## F. Order for the last day

1. Read numbers.md once. 2. Do github_steps.md parts 1 to 3. 3. Record the video from video_script.md. 4. Publish the blog. 5. Paste form_answers.md into the form and add the repo, Pages, video and blog links. 6. Submit before 11:59 PM IST. Aim for 9:00 PM.
