# Real-graph integrity check (block C, isolated rebuild)

**Status: RESOLVED.** Every count below equals the saved baseline exactly, and the real graph each run read
was unchanged across that run.

This file replaces the earlier check on the shared FalkorDB server (port 6380), which recorded a
transient change to `org_xz` with an unknown cause. That cause is still unknown and is not claimed here.

## 1. Isolated instance

- Container: `block_c_final_falkordb`, image `falkordb/falkordb:6.0.2`, volume `block_c_final`.
- Host port: `127.0.0.1:6381`. Ports 6379 and 6380 were not used for any build or run.
- `data/raw` in this worktree is a symlink to the main worktree's `data/raw` (git-ignored public cache).

## 2. Rebuild of org_xz and org_tallowdate (before the runs)

Steps run on the isolated instance:

1. `packs.oss.ingest_xz --twice`: counts identical after both runs (4639 nodes, 4629 edges before claims).
2. `eval.xz_pressure_vouch_status`: wrote the Reader claims from `data/derived/reader_claims.json`
   (coverage 90 / 240 messages read; every quarter NOT_FIRED for both detectors).
3. `eval.xz_normal` (the `normal-xz` step, not named in the request): wrote the 30 Normal nodes and 30 OF edges.
   Without it the rebuild was 30 nodes and 30 edges short, all of them Normal and OF.
4. `redteam.run_tallowdate` (steps 1 to 5): all five PASS, org_tallowdate built.

| Graph | Nodes, rebuilt | Edges, rebuilt | Saved baseline | Match |
|---|---|---|---|---|
| org_xz | 4679 | 4668 | 4679 / 4668 | exact |
| org_tallowdate | 175 | 168 | 175 / 168 | exact |

Label-by-label, org_xz: Action 4569, Actor 69, Normal 30, Claim 3, Source 3, Span 3, Org 1, Path 1;
edges DID 4569, VIA 60, OF 30, ASSERTED 3, FROM 3, HAS 3. Matches the saved breakdown.

Label-by-label, org_tallowdate: Action 155, Actor 6, Normal 12, Org 1, Path 1; edges DID 155, OF 12, VIA 1.
Matches the saved breakdown.

## 3. Red-team and hardening runs (after the rebuild)

All four runs: N = 200, seed = 7. Each run copies its real graph, plants campaigns into copies only, and
records the real graph's counts before and after. Each file records the real graph it ran on; the other
graph's counts are from a measurement taken after all four runs had finished.

| Result file | Real graph read | Before | After | Other graph (after all runs) | Matches baseline | Unchanged |
|---|---|---|---|---|---|---|
| redteam_xz.json | org_xz | 4679 / 4668 | 4679 / 4668 | org_tallowdate 175 / 168 | yes | yes |
| hardening_redteam_xz.json | org_xz | 4679 / 4668 | 4679 / 4668 | org_tallowdate 175 / 168 | yes | yes |
| redteam_tallowdate.json | org_tallowdate | 175 / 168 | 175 / 168 | org_xz 4679 / 4668 | yes | yes |
| hardening_redteam_tallowdate.json | org_tallowdate | 175 / 168 | 175 / 168 | org_xz 4679 / 4668 | yes | yes |

Each xz output carries the label: "run on an isolated rebuild of org_xz, 4679 / 4668; saved baseline 4679 / 4668".

Commit note: the four files record commit `60f5b68`. The xz label in `redteam/run.py` and
`redteam/harden.py` was changed after that commit so that it carries the measured counts. That change is
in the commit that adds this file, so the result files were produced by that commit's code plus the label edit.

## 4. Verdict

The counts from the rebuild and from every run equal the saved baseline exactly, on both graphs and on
every label. Status: RESOLVED on this isolated instance. The earlier transient change on port 6380 is not
explained here, and no cause is claimed for it.
