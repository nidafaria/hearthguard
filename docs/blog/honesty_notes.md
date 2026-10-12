# Honesty pass on post.md

Each draft claim was checked against `docs/blog/facts.md` and its source file. Changes below are the ones made to the first draft. Claims that matched their source were kept unchanged.

## Changes

1. **"That sentence describes the kind of position a takeover needs."** Changed to: the spec quotes the sentence as a public record of a project where one overstretched person holds the keys. *Why:* the source (`docs/HEARTHGUARD.md` line 134) quotes the sentence; it does not say it describes a takeover.

2. **"how many people would have to be persuaded before someone outside could ship"** now cites `docs/HEARTHGUARD.md` §22. *Why:* the definition comes from the glossary, and the paragraph needed a source.

3. **"A median of 0.00382 days ... so commits often arrived in close bursts."** Changed to: half of the gaps were shorter than about five and a half minutes, and the file does not say why. *Why:* a median only says half the gaps were shorter. "Bursts" is an interpretation the file does not make.

4. **"Releases ... rose from 2 to 22."** Changed to give the two endpoint values, 2 at the end of 2021 and 22 at the end of March 2024. *Why:* the series dips to 1 in 2022, so "rose from 2 to 22" would hide that.

5. **"The spec treats takeover cost as the central number."** Changed to the spec's definition: the fewest human approvals an outsider must win. *Why:* "central" is my judgment. The spec's glossary gives the definition.

6. **"HOLD is the honest answer when the moves cannot be told apart."** Changed to: HOLD here means the policy could not tell whether RUSH or BYPASS happened. *Why:* "honest answer" is a value judgment. The build report gives the reason, "move unknown: RUSH, BYPASS".

7. **"The file lists 146 messages remaining, with the next one being msg00507."** Now cites `build_report.md` as well. *Why:* the "next message" value is in the build report, not in `reader_full_run.json`.

8. **"The run used 110,366 input tokens, 44,479 output tokens and 42,803 reasoning tokens."** Changed to "The run reports". *Why:* the file does not say whether reasoning tokens are part of output tokens, so "used ... and ..." (which implies they add up) was not supported.

9. **"The three claims ... show where the reader found something, in three of 94 messages. They do not show how often it is right."** Changed to: the reader returned a claim in three of the 94 messages, and none in the other 91. *Why:* the earlier sentence was vague. The new one states what the counts are, and that they say nothing about accuracy.

10. **"A simulator that cannot yet measure its own effect can be tested, but it does not show that a fix works."** Changed to: on this data, applying a step shows only that the step runs, with no effect on takeover cost. *Why:* the first version said nothing checkable. The new version reports what the file shows.

11. **"Every synthetic entity carries a synthetic flag set to true, so synthetic data cannot pass as real records."** Changed to: every synthetic entity carries a flag set to true, so synthetic data is marked as synthetic in the graph. *Why:* "cannot pass as real records" claims a guarantee that `CLAUDE.md` does not state.

12. **"Every number links to a file in the repository"** (introduction) changed to "Every number cites the file it came from." *Why:* the msg00563 cache is git-ignored and is not in the repository, so "in the repository" was not accurate.

13. **"The short version: ... a small, slowly changing set of committers."** Changed to "between 2 and 7 active commit authors per quarter", with the source. *Why:* "slowly changing" is not measured. The median gap also varies by a factor of about five across the ten quarters, so the set of committers was not shown to be slowly changing.

## Not included, and why

- **The xz maintainer's "unpaid hobby project" line** (`docs/HEARTHGUARD.md` line 134). It is not in the cached message `data/raw/mail/xz-devel/msg00563.html`, so it could not be checked. Left out.
- **Reader recall and precision.** Not computed: no human labels. The post says so and gives no figure.
- **Census, patience curve, memory ablation, finance-team section.** No output file exists in `eval/results/`. The post says they are not measured and gives no figure.
- **The tallowdate synthetic story's outputs.** Not cited. The post says the story is synthetic in every mention and reports none of its numbers.
- **The "six places" and the Slack thread.** No measured output for either is in the six results files the brief lists, so neither is described.
- **Quoting the maintainer by any other message.** Only msg00563 was used. `eval/results/video_quotes.json` does not exist.

## Words the checker bans

The draft was searched for "wins", "solves", "proves", "perfect" and "guaranteed". None was used. The checker enforces this.
