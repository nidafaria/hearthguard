# Demo video script (about 3:40)

Target length: 3 to 4 minutes, as asked. Warning: the older spec (docs/HEARTHGUARD.md §14, docs/submission_checklist.md) says "3 minutes or less". The rules page text I fetched gives no length limit. If the form says a limit, cut the blocks marked (CUT FIRST).

Setup before you press record:
- Open `demo/index.html` in Chrome from your disk (no internet needed). Use the arrow keys to move between screens, or type the address ending `#/overview`, `#/replay`, `#/hardening` and so on.
- Have a terminal open in the repo with `uv run python -m eval.demo` ready (it prints from saved files; needs no key, no database).
- Keep `docs/submission/numbers.md` on a second screen. Say only numbers from it.
- Speak slowly. Plain words. Say "not computed" out loud where it is true.

Every number below carries its source file. The "N#" is the row in numbers.md.

| Time | Open on screen | Say (read it as written) | Length | Numbers and their files |
|---|---|---|---|---|
| 0:00 to 0:20 | `demo/index.html` at `#/overview` | "Some attacks are too slow for anything that forgets. Hearthguard keeps a memory of who could change an open-source project, and how that changed over time. It stores that memory as a graph in FalkorDB." | 20 s | none |
| 0:20 to 0:50 | The saved xz-devel quote screen, or terminal output of `uv run python -m eval.demo` | "This is real, public data: the xz project. In May 2022 the maintainer wrote on the public mailing list: 'It's clear that my resources are too limited.' The public git history has 4,569 recorded actions from 68 author identities. The names are hashed." | 30 s | Quote: eval/results/video_quotes.json (Q1, date May 2022). 4,569 and 68: eval/results/xz_ingest.json (N1, N2) |
| 0:50 to 1:20 | `#/quarter` then `#/evidence` | "It remembers what normal looks like, then checks four slow moves: pressure, vouch, rush and bypass. Each is a fixed rule written as code and tested. The language model only reads text into claims. It never decides." | 30 s | none (rule source: docs/HEARTHGUARD.md §8.4) |
| 1:20 to 2:00 | `#/replay` | "Here is the replay on real xz, quarter by quarter. The answer is HOLD in all ten quarters. That means: not enough data to say. The public record has no grant of release rights. We searched 14 sources and found 0 grant records. So takeover cost on real xz is not computed. We do not guess a number. The reader model read 94 of 240 messages and then hit its daily limit. Four were too long to read. Its precision and recall are not computed, because nobody has labelled the test set yet." | 40 s | HOLD x10: eval/results/decision_status.json (N9). 14 and 0: eval/results/xz_grant_search.json (N7). 94, 240: eval/results/reader_full_progress.json (N10). 4: eval/results/reader_full_run.json (N12). Precision: eval/results/reader_testset.json (N14) |
| 2:00 to 2:25 | A plain text card, or the README "Limitations" section | "Honest limits. The xz backdoor was in the release tarballs, not in git, so a git replay cannot show it. This build does not detect the xz backdoor and does not claim to. There is no public grant record for real xz. The Slack send path is tested with a fake sender. No real Slack message was sent." | 25 s | Sources: eval/results/xz_normal.json (notes); eval/results/slack_preview.json and eval/results/blockers_slack_sender.md (N31). If Window 3 really changed Slack, change the last sentence and show proof. No file in the repo says it did |
| 2:25 to 3:00 | Terminal or `#/hardening`. Say SYNTHETIC out loud first | "Now a made-up case. These are planted attacks, not findings about any real project. In a synthetic project called tallowdate, three new accounts were created on February 10, 11 and 12. One reviewer has 140 reviews on record. The takeover cost here is also not computed. We planted 200 attack campaigns into it. The frozen detectors caught 182. That is 0.91." | 35 s | Dates: eval/results/tallowdate_demo_script.json (N25). 140: eval/results/tallowdate_load.json (N26). 200, 182, 0.91: eval/results/redteam_tallowdate.json (N16) |
| 3:00 to 3:25 | `#/patience` or `#/two` (Track 02: memory) | "This is why memory matters. Same 100 campaigns. With full memory the detection rate is 0.88. If the system only remembers the last 90 days, 0.82. The last 30 days, 0.60. And on a clean set of 20, full memory flagged 1. The forgetful versions flagged all 20." | 25 s | eval/results/ablation_memory.json (N19) |
| 3:25 to 3:45 | `#/hardening` | "We can also test a fix. On a copy of the xz history with planted campaigns, adding a second keeper raises the number of guardians from 1 to 2. But the caught campaigns drop from 167 to 152 of 200. This build does not explain that drop. We report it as it is. Hearthguard shows what it can check, and says not computed where it cannot." | 20 s | eval/results/hardening_redteam_xz.json (N18) |
| 3:45 to 3:50 | Title card: repo link and Pages link | "Code and demo are linked below. Thank you." | 5 s | none |

## Cut list (if you must shorten)

1. (CUT FIRST) The 3:25 hardening block.
2. The 3:00 memory block (it is the strongest Track 02 point, so cut it last of these).
3. The 0:50 explanation: keep one sentence.

## Do not say

- A takeover cost for real xz. "Six public places". A Reader precision or recall. That the tool "would have caught" xz. Any maintainer reaction. A test count until you re-run it (numbers.md row 27: 467 in the saved file, 959 in the README).
- Do not claim a live Slack message, a live deployment, or a census. None exists.

## After recording

Watch it once with the sound off. Every screen with synthetic data must show the word SYNTHETIC (the demo page does). Upload as unlisted or public, put the link in README, blog and form.
