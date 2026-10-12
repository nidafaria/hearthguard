# 0005: Pressure's keeper-activity condition

**Status: OPEN.** The condition is open in the freeze draft (docs/FREEZE.md, Pressure; spec §7.6 corrected in "Spec fix d").

## What is open

Pressure fires only if (1) there are >= 3 PRESSURE or URGENCY claims from >= 2 low-history actors in 120 days, AND (2) the keepers' activity in the last 90 days is <= 50% of the org's own trailing-two-year median, OR a keeper CAPACITY_STATEMENT exists in the window.

For (2) we need to know who the keepers are. For xz there is no grant record (eval/results/xz_grant_search.json), and the proposed readings of "active keepers" are themselves open (decision 0001, item 2).

## What the code does meanwhile

`core/detectors/pressure.py` computes condition (1) from the graph.

- If (1) fails, Pressure is **NOT_FIRED**: the AND cannot hold whatever (2) is.
- If (1) holds, Pressure is **NOT_COMPUTED** with the reason "keeper activity condition open in freeze".

It never returns FIRED on real data. No threshold was changed. The metric `keeper_activity_median_90d` stays NOT COMPUTED in `eval/results/xz_normal.json`.

## To close it

The owner picks what counts as a keeper (committers in the last N days; or holders of a grant once grants are known), then the freeze file is dated and updated.
