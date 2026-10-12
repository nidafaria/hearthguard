# Hearthguard demo video: shot list

Built from docs/HEARTHGUARD.md §14, cut to what the current build shows. Checked by `make video-check`
(eval/video_check.py). Every quote is matched word for word in data/raw/mail/xz-devel/. Every number is
read from the file named in its Source line. Act II is synthetic and labelled on screen.

**Total:** 2:02

Scene format: time range, act, screen, on-screen text, narration, then one Quote or Number line per
quoted or shown value, and a Source line that names the file behind each one.

## S1 · 0:00–0:06 · Act I (real)
- **Screen:** Black, then the cached public post (data/raw/mail/xz-devel)
- **On screen:** xz-devel mailing list · May 2022
- **Narration:** (silence)
- **Quote:** Q1 · msg00563.html — "It's clear that my resources are too limited."
- **Number:** DATE_Q1 = May 2022
- **Label:** none
- **Source:** data/raw/mail/xz-devel/msg00563.html; eval/results/video_quotes.json

## S2 · 0:06–0:14 · Act I (real)
- **Screen:** Same kind of public post, the words "unpaid hobby project" highlighted
- **On screen:** xz-devel mailing list · June 2022
- **Narration:** The project was an unpaid hobby project. The maintainer wrote that their own resources were too limited.
- **Quote:** Q2 · msg00567.html — "unpaid hobby project"
- **Number:** DATE_Q2 = June 2022
- **Label:** none
- **Source:** data/raw/mail/xz-devel/msg00567.html; eval/results/video_quotes.json

## S3 · 0:14–0:20 · Act I (real)
- **Screen:** Public post from late June, the quoted words highlighted
- **On screen:** xz-devel mailing list · 29 June 2022
- **Narration:** In late June 2022, the maintainer wrote that a helper who worked off the list was practically a co-maintainer already.
- **Quote:** Q3 · msg00571.html — "Practically a co-maintainer already."
- **Number:** DATE_Q3 = 29 June 2022
- **Label:** none
- **Source:** data/raw/mail/xz-devel/msg00571.html; eval/results/video_quotes.json

## S4 · 0:20–0:28 · Act I (real)
- **Screen:** Saved ingest result: the node counts for the public xz git history
- **On screen:** xz git history (public) · 4,569 actions · 68 actors
- **Narration:** The public git history of xz has 4,569 recorded actions. They come from 68 author identities. The names are hashed.
- **Number:** ACTIONS = 4,569
- **Number:** ACTORS = 68
- **Label:** none
- **Source:** eval/results/xz_ingest.json

## S5 · 0:28–0:36 · Act I (real)
- **Screen:** Title card
- **On screen:** HEARTHGUARD · Some attacks are too slow for anything that forgets.
- **Narration:** Hearthguard reads a project's history. It remembers what normal looks like.
- **Label:** none
- **Source:** docs/HEARTHGUARD.md §7 (the moves and the remembered normal)

## S6 · 0:36–0:46 · Act I (real)
- **Screen:** Card listing the four moves the detectors check
- **On screen:** Pressure · Vouch · Rush · Bypass
- **Narration:** It checks for four moves: pressure, vouch, rush and bypass. Each one is a fixed rule. No AI model decides them.
- **Label:** none
- **Source:** docs/HEARTHGUARD.md §7; docs/HEARTHGUARD.md §8.4 (the model is never in the decision path)

## S7 · 0:46–1:02 · Act I (real)
- **Screen:** Replay table from saved results (no network, no key)
- **On screen:** Reader: 94 of 240 messages · 4 too long to read · every quarter HOLD
- **Narration:** A reader model has worked through 94 of the 240 messages in scope. Four were too long to read. Replaying the history, every quarter is held. Some checks had too little data to decide.
- **Number:** READER_DONE = 94
- **Number:** READER_TOTAL = 240
- **Number:** READER_TOO_LONG = 4
- **Label:** none
- **Source:** eval/results/reader_full_progress.json; eval/results/reader_full_run.json; eval/results/decision_status.json

## S8 · 1:02–1:10 · Act II (synthetic)
- **Screen:** Card for the synthetic case
- **On screen:** SYNTHETIC demo case · tallowdate · fictional project, fictional people
- **Narration:** This is a made-up project called tallowdate. Every person in it is invented.
- **Label:** SYNTHETIC
- **Source:** data/synthetic/tallowdate.json (its label field)

## S9 · 1:10–1:20 · Act II (synthetic)
- **Screen:** Saved demo-script beat for this case (not a live Slack message)
- **On screen:** SYNTHETIC · saved demo beat · Takeover cost: NOT COMPUTED
- **Narration:** The demo for this case says the takeover cost is not computed. It does not guess a number.
- **Label:** SYNTHETIC
- **Source:** eval/results/tallowdate_demo_script.json; eval/results/tallowdate_detector_status.json

## S10 · 1:20–1:32 · Act II (synthetic)
- **Screen:** Saved demo-script beat: the three account-created events
- **On screen:** SYNTHETIC · accounts created 2026-02-10 · 2026-02-11 · 2026-02-12 · other projects: NOT COMPUTED
- **Narration:** Three new accounts were created within one week. Whether they touched other projects is not computed yet.
- **Number:** ACCOUNT_A = 2026-02-10
- **Number:** ACCOUNT_B = 2026-02-11
- **Number:** ACCOUNT_C = 2026-02-12
- **Label:** SYNTHETIC
- **Source:** eval/results/tallowdate_demo_script.json

## S11 · 1:32–1:42 · Act II (synthetic)
- **Screen:** Saved fact for the synthetic case
- **On screen:** SYNTHETIC · reviews by the reviewer in this case: 140
- **Narration:** In this case, one reviewer has 140 reviews on record.
- **Number:** TOMAS_REVIEWS = 140
- **Label:** SYNTHETIC
- **Source:** eval/results/tallowdate_load.json

## S12 · 1:42–1:52 · Build check (real)
- **Screen:** Saved result of the full test suite
- **On screen:** Full test suite · 467 passed, no failures
- **Narration:** The build's test suite has 467 passing tests and no failures.
- **Number:** TESTS_PASSED = 467
- **Label:** none
- **Source:** eval/results/final_tests.json

## S13 · 1:52–2:02 · Close
- **Screen:** Closing card
- **On screen:** HEARTHGUARD · shows what it can check, says NOT COMPUTED where it cannot
- **Narration:** Hearthguard shows what it can check. Where it cannot check, it says not computed.
- **Label:** none
- **Source:** docs/HEARTHGUARD.md §14 (closing line, reworded to what the build shows)

---

## Cut from §14 (no saved result, or the build does not show it)

- 0:16 "Who saw what", six rows, takeover cost 1: the six public places are NOT COMPUTED (completion_full.md: ecosystem records NOT STARTED); takeover cost for xz is NOT COMPUTED (xz_takeover_status.json).
- 0:48 Debian visibility gap and the "note appears on the date it fired": no measured dates; Pressure and Vouch did not fire and Rush and Bypass were not checked.
- 0:36 "Every takeover makes four moves ... they're the attack": the build does not show intent, and the xz git history is not the backdoor (xz_ingest.json note).
- 1:12 to 2:00 live Slack beats (DM, Show me why in Slack, Simulate a fix, Draft a reply, "It's fine" adopted, "tested against 200 attacks"): slack_preview.json has sent_to_slack false; no hardening result for tallowdate exists.
- 2:14 May Rush note and the two keepers declining: Rush is NOT COMPUTED for tallowdate.
- 2:24 finance controller and Claude Code check_trust: no finance pack or check_trust result exists.
- 2:32 montage (memory ablation, census aggregate, identical findings across orderings, ₹0): no saved results.
- 2:42 weekly digest DM: not built.
- 2:52 two-endings gauges (1 and 2): both gauges are NOT COMPUTED. The narration of the ending was rewritten to match.
