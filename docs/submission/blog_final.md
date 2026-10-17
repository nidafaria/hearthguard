# "It's clear that my resources are too limited": what the public xz record measures

In May 2022, the maintainer of xz Utils wrote on the public xz-devel list: "It's clear that my resources are too limited." The message is cached in `data/raw/mail/xz-devel/msg00563.html`, dated 19 May 2022 (the cache is git-ignored, so a fresh clone does not have it). The project's spec quotes that sentence as a public record of a project where one overstretched person holds the keys. Source: `docs/HEARTHGUARD.md` (line 134).

Hearthguard is a tool that tries to measure that kind of position. It asks who holds the keys to a project, how fast trust was granted in the past, and how many people would have to be persuaded before someone outside could ship. Source: `docs/HEARTHGUARD.md` (§22, glossary). This post reports what it measured on the public xz history, and what it could not. Every number cites the file it came from, and some numbers are not computed at all. The post says which.

The short version: the public git history shows between 2 and 7 active commit authors per quarter. Source: `eval/results/xz_normal.json`. It does not show the backdoor, and it has no record of who was granted release rights. Three detectors could not be computed for that reason. Source: `eval/results/xz_detector_status.json`. The language-model reader stopped partway through its run, and it has not been checked against human labels. Source: `eval/results/reader_full_progress.json`.

## What the public git history shows

The normal-metrics file covers ten quarter-ends, from the end of 2021 to the end of March 2024. It uses the public xz git repository only, at head 3b1efb04, fetched on 12 October 2026. Source: `eval/results/xz_normal.json`.

The backdoor was not in that history. The file says it was in release tarballs, not in git, so these numbers do not show it. Source: `eval/results/xz_normal.json`. This is the most important limit in the post.

Active keepers, counted as distinct commit authors over 90 days, went 4, 3, 3, 3, 2, 2, 5, 7, 5, 7 across the ten quarter-ends. Source: `eval/results/xz_normal.json`. The same file warns that an author is not always someone with commit access, so this count can overstate the number of keepers. Source: `eval/results/xz_normal.json`.

The median gap between commits was 0.00523 days at the end of 2021. It peaked at 0.01858 days at the end of June 2022, and was 0.00382 days at the end of March 2024. Source: `eval/results/xz_normal.json`. The number of gaps counted rose from 201 to 1584 over the same period. Source: `eval/results/xz_normal.json`. A median of 0.00382 days is about five and a half minutes. The file does not say why the gaps are so short. Source: `eval/results/xz_normal.json`.

The count of releases in the 730-day window was 2 at the end of 2021 and 22 at the end of March 2024. Every release went through git. Source: `eval/results/xz_normal.json`. The file says git is the only channel this ingest can see, so the path column says nothing about tarballs or CI. Source: `eval/results/xz_normal.json`.

## What could not be computed

Three detectors ran on release v5.6.1, with T set to 2024-03-31 23:59:59 UTC. Source: `eval/results/xz_detector_status.json`. Rush, bypass and lone keeper all returned NOT COMPUTED, and the file is marked provisional. Source: `eval/results/xz_detector_status.json`.

Rush needs a grant record. The git history has no record of a release privilege being granted, so there was nothing to measure. Source: `eval/results/xz_detector_status.json`. A search of 14 sources found 0 grant records. One commit-message match was read and is a THANKS sorting change, not a grant. Source: `eval/results/xz_grant_search.json`.

Bypass needs variation in the release path. The xz ingest gives every release the same path node, so there was nothing to compare. Source: `eval/results/xz_detector_status.json`.

Lone keeper depends on guardians, and guardians depend on grant data. Both are missing, so lone keeper is also not computed. Source: `eval/results/xz_detector_status.json`.

The spec defines takeover cost as the fewest human approvals an outsider must win. On this data it is not computed, for the same missing grant data. Source: `eval/results/xz_hardening.json`, and `docs/HEARTHGUARD.md` (§22). This post therefore has no takeover cost figure. A number that looked like one would be invented, and the project rules forbid that. Source: `CLAUDE.md`.

Pressure and Vouch returned NOT_FIRED in all 10 quarters, on the messages the reader read. Source: `eval/results/decision_status.json`. That result is weak. The reader returned no pressure, urgency or vouch claim, and its recall has not been measured. A quiet reader and an absent signal look the same in this output. Source: `eval/results/decision_status.json`, and `eval/results/reader_full_run.json`.

The decision was HOLD in all 10 quarters, with the reason "move unknown: RUSH, BYPASS". Source: `eval/results/decision_status.json`. Here HOLD means the policy could not tell whether RUSH or BYPASS happened. It is not a verdict on the project. Source: `eval/results/decision_status.json`.

## The reader, and where it stopped

The spec allows a language model in a few roles. One is reading messages and extracting typed claims. It is never in the decision path: detectors, the decision policy, takeover cost and guardians are plain code with unit tests. Source: `CLAUDE.md`.

The reader run covers 240 messages in scope. It stopped at 94, because the daily token limit of 200,000 tokens was reached. Source: `eval/results/reader_full_progress.json`. The file lists 146 messages remaining, with the next one being msg00507. Source: `eval/results/reader_full_progress.json`.

Of the 94 messages, the reader extracted 3 claims, all of kind CAPACITY_STATEMENT. It rejected 6 quotes because they were not exact substrings of the message text. 91 messages had no claim. Source: `eval/results/reader_full_run.json`.

Four messages were recorded as not read because they were too long to send. Source: `eval/results/reader_full_run.json` (messages_not_read_too_long). The run reports 110,366 input tokens, 44,479 output tokens and 42,803 reasoning tokens. Source: `eval/results/reader_full_run.json`.

The reader was not measured against human labels, so its precision and recall are NOT COMPUTED. Source: `eval/results/reader_testset.json`. The 60 messages in the test set are held back for human labels and were not read. Source: `eval/results/reader_full_run.json`, which excludes them. The reader returned a claim in three of the 94 messages, and it returned none in the other 91. Those counts say nothing about how often it is right. Source: `eval/results/reader_full_run.json`.

## The hardening simulator

The hardening simulator copies the org graph, applies one safety step, and reports before and after. On the public xz history it ran for 10 quarter-ends. Source: `eval/results/xz_hardening.json`.

In every quarter, the step require_provenance_ci applied. In the first quarter it set 10 properties and created no nodes. Source: `eval/results/xz_hardening.json`. The org graph had 4679 nodes and 4668 edges before and after. Source: `eval/results/xz_hardening.json`.

The other two steps, add a second keeper and require two approvals, did not apply in any quarter. The graph had no grant or Privilege data to act on. Source: `eval/results/xz_hardening.json`.

Takeover cost is NOT COMPUTED before and after every step, so this file shows no change on the number the simulator exists to move. Source: `eval/results/xz_hardening.json`. This file records no red-team result, so it cannot say whether any planted campaign would have been caught, or how early.

The red-team hardening run is in a separate file. It plants synthetic campaigns into a copy of the public xz history; the file says it is not a finding about xz. Adding a second keeper raises guardians from 1 to 2 and lowers the caught campaigns from 167 to 152 of 200. The other two steps change neither takeover cost, guardians nor the caught count. This build does not explain the drop in caught campaigns. Source: `eval/results/hardening_redteam_xz.json`.

## What is not measured yet

The spec plans more sections: a census of public packages, a patience curve, and the same moves in a finance team. The census has no output file in the results folder, so it is not measured. Source: `docs/HEARTHGUARD.md` (§6.4, §11.2) and the file list of `eval/results/`. The memory ablation (`eval/results/ablation_memory.json`) and the algorithm ablation (`eval/results/ablation_algos.json`) have output files, but this post does not report their numbers.

## Where the project stands

The completion file gives the project a score of 70.6 percent. It counts 75 rows DONE, 35 PARTIAL and 21 NOT STARTED, out of 131, with DONE worth 1 and PARTIAL worth 0.5. Source: `eval/results/completion_full.md`. It is a self-assessment against the spec rows, not an external audit.

## Ethics by design

The project's rules say it uses public, synthetic or its own data only, that identifiers are hashed on ingest, and that per-project output is not published. Source: `CLAUDE.md` (Data and privacy). The repository was local only when this was written (`eval/results/completion_full.md`, row 3). It is public from the day it is submitted.

Detectors are not allowed to read the planted-campaign flags. Only the scorer reads them. Planted entities carry `synthetic: true`, `planted: true` and a `campaign_id`. Source: `redteam/generate.py`, and `CLAUDE.md`.

The post names no one beyond the maintainer's public words. It does not speculate about anyone's life, health or motives. Source: `docs/HEARTHGUARD.md` (line 134).

## The synthetic story

The demo's second act is a synthetic story called tallowdate. It is synthetic data, not a real organisation's records, and this is true in every mention of it. This post reports none of its outputs. Source: `docs/HEARTHGUARD.md` (§22).

## What comes next

The reader needs the remaining 146 messages. Source: `eval/results/reader_full_progress.json`. The test set of 60 messages needs human labels before the reader can be scored. Source: `eval/results/reader_testset.json`. The grant problem needs a source that records who was granted release rights. Source: `eval/results/xz_grant_search.json`. The keeper condition for Pressure is still an open decision. Source: `docs/decisions/0005-pressure-keeper-activity-open.md`.

The public git history does not contain the backdoor, and it contains no grant record. That is the limit of this post, and the first thing a reader should take from it. Source: `eval/results/xz_normal.json` (notes) and `eval/results/xz_grant_search.json`.
