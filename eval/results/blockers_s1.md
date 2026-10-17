# Blockers: s1 (branch coding/s1-defaults)

Rows that were checked for "stuck only on an open decision" and could not be finished. Defaults for
every open decision are recorded in docs/decisions/ (2026-10-18). Finished here: rows 13 and 80.

| Row | Why it is still not finished |
|---|---|
| 17 Core free of domain code | The kind names in `core/normal/metrics.py` could move to the pack, but the property table in `core/detectors/bypass.py` is a detector, which may not change here. The row cannot be completed. |
| 37, 72 Contradiction links | Needs a new pair detector with a frozen rule; no default decision supplies one. |
| 46 Pressure | Default keeps it NOT_COMPUTED (decision 0005); the frozen detector may not change. |
| 47 Vouch | Needs a candidate target and SHARES edges; the data is not in the cache (decision 0004). |
| 50 Lone keeper | Needs grant records; none exist for xz. The detector is frozen. |
| 66 Learned exceptions | Decision 0007 default accepted, but Adopted acting on a live decision needs actor-level move records the saved suite lacks. |
| 102 Simulate a fix | Finishing it needs the expectation in `tests/integration/test_inbox_loop.py` changed, which is forbidden here. |
| 8 Named module owners | People's names; only the team can assign them. |
| 36, 59 SHARES / Watcher | Needs account dates and email domains that are not in the cache. |
| 77 Freeze protocol | Needs the owner to date the freeze; `docs/FREEZE.md` may not be edited here. |
