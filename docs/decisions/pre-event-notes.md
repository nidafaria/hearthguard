# Pre-event notes (Oct 12, 2026)

Short record of what was decided before the event. Plain words. Full rules are in docs/FREEZE.md.

## 1. Spec fixes

The spec had six mismatches. FREEZE.md fixes each one and lists it at the bottom.

- a. TRUSTS is not in the data model. The freeze uses CAN_GRANT and GRANTED. TRUSTS is marked PROPOSED.
- b. The trust-path query used names not in the model. It now uses CAN_GRANT and GRANTED, and weight 'approvals'.
- c. The visibility-gap query runs on the ecosystem graph (ecosystem_<id>). Three of its edges are missing from the model and are PROPOSED.
- d. The Pressure query used a value that is not stored. It now counts actions up to time T.
- e. Bypass alone can send a note. Any other note needs 2 or more moves. The spec agreed with itself but did not say it.
- f. The census source is unknown. The census is NOT FROZEN until the source is filled in.

## 2. Open items

- The census list is still open. Name, URL and fetch date are missing.
- The false-alarm repo list is still open. The selection rule is PROPOSED.
- Three gaps in the spec are not yet fixed: how OUTSIDER connects to actors; the Pressure query has no keeper-activity check; the Bypass query covers only part of the OSS rules.

## 3. Later work

- Red-team parameters and the tallowdate story beats: write them from spec §3.5 and §8 when they are needed. No text was copied in from elsewhere.
- Slack message and modal mock-ups: the spec (§17) asks for them as notes. Not written yet.

## 4. Local state

- The project is not a git repo. Nothing is committed.
- The freeze hash is in docs/FREEZE.sha256. Re-record it if FREEZE.md changes.
