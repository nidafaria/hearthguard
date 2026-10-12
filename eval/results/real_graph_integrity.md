# Real-graph integrity check (block C)

Question: did any red-team run change the real graphs `org_xz` or `org_tallowdate`, and if so, what
wrote to the same FalkorDB server (port 6380) at that time?

Short answer: **the cause of the observed transient change is unknown.** Other writers were
present on the server during the runs (other blocks' pytest processes), but nothing I measured
links any of them to a change in `org_xz` or `org_tallowdate`. Inside my own code, planting only
writes to copies (`redteam_*`, `harden_*`, `org_rt*`); a direct probe of the scaffold step left
both real graphs unchanged.

## 1. Before and after counts, per run

Counts are nodes and edges from `MATCH (n) RETURN count(n)` and `MATCH ()-[r]->() RETURN count(r)`.

| Run (block-c) | Time (IST) | org_xz before | org_xz after | org_tallowdate before | org_tallowdate after | Recorded as unchanged |
|---|---|---|---|---|---|---|
| `redteam --n 12 --case tallowdate` | ~20:30 | not recorded | not recorded | not recorded | not recorded | True (console only; file overwritten) |
| `redteam --n 200 --case tallowdate` (first) | ~20:40 | not recorded | not recorded | 199 / 192 | 175 / 168 | False (console; file overwritten) |
| `redteam --n 200 --case tallowdate` (clean rerun) | 20:47 | not recorded | not recorded | 175 / 168 | 175 / 168 | True (`eval/results/redteam_tallowdate.json`) |
| `redteam --n 3 --case xz` (test) | ~21:0x | 4725 / 4733 | 4679 / 4668 | not recorded | not recorded | False (`eval/results/redteam_xz.json`) |
| `redteam --n 200 --case xz` (killed by me, no output) | ~20:55 | not recorded | not recorded | not recorded | not recorded | no result file |
| `harden --n 20 --case tallowdate` (test) | ~21:0x | not recorded | not recorded | not recorded | not recorded | the harden script does not record real-graph counts |
| `harden --n 200 --case tallowdate` (crashed, no output) | ~20:55 | not recorded | not recorded | not recorded | not recorded | no result file |
| Scaffold probe (`make_template` on xz) | 21:0x | 4679 / 4668 | 4679 / 4668 | 175 / 168 | 175 / 168 | yes (direct probe) |
| Live sampler, 60 samples | 21:04:42 to 21:09:41 | 4679 / 4668 (all 60) | 4679 / 4668 | 175 / 168 (all 60) | 175 / 168 | n/a |

Notes on this table:
- The 199 / 192 and 4725 / 4733 "before" values were measured at the start of those runs, but
  the files and console output that carried them were overwritten or the runs were killed. The
  values above are what the tool output showed at the time.
- The current `org_xz` and `org_tallowdate` counts (4679 / 4668 and 175 / 168) match the saved
  baselines, `eval/results/xz_*` and `eval/results/tallowdate_load.json`.

### Label and type breakdown (measured 21:0x, after the transient)

`org_xz`: 4679 nodes, 4668 edges. Labels: Action 4569, Actor 69, Normal 30, Claim 3, Source 3,
Span 3, Org 1, Path 1. Relationship types: DID 4569, VIA 60, OF 30, ASSERTED 3, FROM 3, HAS 3.

`org_tallowdate`: 175 nodes, 168 edges. Labels: Action 155, Normal 12, Actor 6, Org 1, Path 1.
Relationship types: DID 155, OF 12, VIA 1. Planted-flag nodes: 14 (from the existing synthetic case).

**Not captured:** the label and type breakdown during the transient (the peak of 4725 / 4733 on
`org_xz`, and 199 / 192 on `org_tallowdate`). I did not take a breakdown at those moments, so I
cannot say which labels or edge types were added and then removed. This is a gap in the record.

## 2. Other processes on port 6380 during my runs

Measured at about 21:01 to 21:05 on the Windows host, while my runs were active:

Python and pytest processes of other blocks (command lines, shortened where long):
- `C:\Users\farze\newhackathon-block-d\.venv\Scripts\pytest.exe` (pids 17736, 1620, 12888),
  started 21:01:12
- `C:\Users\farze\newhackathon-block-b\.venv\Scripts\pytest.exe -q -p no:cacheprovider`
  (pids 19016, 22708, 22164), started 21:02:48
- `C:\Users\farze\newhackathon-block-a\.venv\Scripts\pytest.exe -q -rfE -p no:cacheprovider`
  (pids 23120, 18596, 4628), started 21:03:49
- `uv run pytest -q -rfE -p no:cacheprovider` (hermes uv, pids 20888, 22980), and
  `uv run pytest -q -p no:cacheprovider` (hermes uv, pid 18836)

The block-a, block-b and block-d test suites call the loaders for `org_tallowdate`
(`tests/integration/test_tallowdate_load.py`) and for `org_xz` (`tests/integration/conftest.py`
loads `org_xz` if it is missing). Their `test_xz_ingest.py` uses the scratch graph `org_xz_test`,
not `org_xz`. I found no test in those suites that drops or copies `org_xz` or `org_tallowdate`.

Server-side clients (`CLIENT LIST` at about 21:05): 11 other FalkorDB clients from `172.26.0.1`,
all running `graph.QUERY`, connected 54 to 66 seconds before. These clients cannot be matched to a
Windows process: the TCP table shows only `wslrelay.exe` (11 connections) and
`com.docker.backend.exe` (1 connection) on port 6380.

Server command counters, over the sampler window (21:04:42 to 21:09:41), cumulative since the
server started:
- `cmdstat_graph.QUERY`: +7015
- `cmdstat_graph.RO_QUERY`: +1794
- `cmdstat_graph.DELETE`: +2488
- `cmdstat_graph.COPY`: +212
- `cmdstat_graph.CONSTRAINT`: +252
- `cmdstat_graph.LIST`: +99

So other clients were writing and deleting on the server during that window. Those counters do
not say which graphs they touched. `org_xz` and `org_tallowdate` stayed constant in the same
window.

Processes from my own work (for the record): redteam runs, the harden run and the integrity
sampler, all from `C:\Users\farze\newhackathon-block-c\.venv\Scripts\python.exe`. I stopped the
xz run (pids 21668 and 18728) before the check.

## 3. My own writes, found during this check

- The N=200 hardening run crashed with `Invalid graph operation on empty key` (log: harden200).
  Cause: during the run I dropped leftover `org_rt*` copies (`org_rt4750dca231`,
  `org_rtaed3879c00`, `org_rt6ce0059752`). The hardening run was using `org_rt*` copies for
  scoring at that time, so the drop removed one in use. This is my error, and it touched only
  copies, not real graphs.
- Leftover `redteam_*` and `takeover_*` graphs from earlier crashed runs remain on the server.
  I did not delete them: `takeover_*` may belong to other blocks.

## 4. Verdict

- **Confirmed writers on the server during my runs:** yes. Block-a, block-b and block-d test
  processes were running, and the server counters show writes and deletes by other clients.
- **Confirmed writer to `org_xz` or `org_tallowdate`:** none. No other process has been shown to
  have written to either real graph, and the cause of the transient change is **unknown**.
- **Planting code path:** the scaffold probe and the campaign copies write only to copies. The
  probe left both real graphs unchanged.
- **Not done:** no new run until the four blocks use separate databases or graph names.

## 5. Recommended fix (not applied)

Give each block its own FalkorDB port or its own graph-name prefix, and make the real-graph
check read counts from a graph only the block owns. Until then, the "real graph unchanged"
result cannot be trusted for any run that overlaps other blocks' tests.
