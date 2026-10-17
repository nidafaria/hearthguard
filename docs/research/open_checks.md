# Open checks

Branch `research/open-checks`. Read-only research; nothing pushed, merged or deleted.

## Check 1: `takeover_714356ec4899`

- **Does it exist?** No. It is in neither project FalkorDB:
  - `newhackathon-falkordb-1` (port 6380): `GRAPH.LIST` has no such graph; `GRAPH.RO_QUERY` returns "Invalid graph operation on empty key".
  - `hh-clean-run-2026-10-17-falkordb-1` (port 6390): same.
  - So there are no node or edge counts to report.
- **Not checked:**
  - The five `cascade*` containers (FalkorDB v4.22.0, password required). Different project, not touched.
  - The stopped `block_*` containers (`block_c_final`, `block_f`, `block_g`, `block_h`, `block_i`). The graph could still be in one of those volumes.
- **Repo search:** the string `714356ec4899` appears nowhere in the repo.
- **Creating code:**
  - `core/takeover/scratch.py:117`: `name = f"takeover_{run or uuid.uuid4().hex[:12]}"`.
  - `core/takeover/scratch.py:115-122`: `scratch_graph()` is a context manager that drops the graph in `finally`.
  - Callers: `core/takeover/cost.py:75`, `core/takeover/guardians.py:77`, `core/takeover/trust_path.py:121`.
- **Would a test recreate it?** Yes, in the normal case. Tests that run `takeover_cost`, `guardians` or `trust_path` create a `takeover_<12 hex>` graph and drop it on exit. Several tests assert none are left behind (for example `tests/integration/test_takeover.py:36`, `test_detectors.py:240-242`, `test_trust_path.py:94`). A leftover needs a process killed mid-run. I did not run the suite.
- **Recommendation:** nothing to delete. It is already absent from both databases. If it turns up in a `block_*` volume, it is a crash leftover; delete it then, with approval.

## Cleanup candidates

**Candidates for cleanup, approval needed.** None were deleted.

Matched `redteam_*`, `org_tst*`, `org_rt*`, `takeover_*`, plus `harden_*`. Node counts are from a read-only query.

### Port 6380 (`newhackathon-falkordb-1`)

| Graph | Nodes | Origin |
|---|---|---|
| `redteam_cfeb3abfb5` | 4679 | left by my first rerun, killed at 550 s (present before the current rerun started) |
| `redteam_ef5c1684e1` | 4745 | same |
| `org_rta080c2549e` | 4767 | same |
| `org_tst1dcb347d2b`, `org_tst1aed6fde02` | n/a | seen earlier; gone by the later listing (most likely a test run elsewhere cleaned up) |
| `harden_b526c8b473`, `redteam_00ccbd26bf`, `org_rta8b49fd554` | 4745 / 4745 / empty | **in use by the live rerun (PID 1536). Do not delete.** Names change as the run advances; the run drops them itself |

### Port 6390 (`hh-clean-run-2026-10-17-falkordb-1`)

| Graph | Nodes | Origin |
|---|---|---|
| `org_rtbd43dbc733` | 4770 | left by my first rerun on this port, killed at 550 s |
| `redteam_66f3d50c3c` | 4744 | same |
| `redteam_eda31b1227` | 4678 | same |

No `takeover_*` graph exists on either port.

## Check 2: hardening number 152

- **Committed value:** `eval/results/hardening_redteam_xz.json`, step `add_second_keeper`, `campaigns.after`:
  - `caught: 152`, `missed: 48`, `caught_rate: 0.76` (line 59), `median_lead_time_days: 1.1416670000000004`.
  - Before: `caught: 167`, `caught_rate: 0.835`.
  - Guardians 1 to 2; takeover cost 1 to 1.
  - Generated `2026-10-13T12:59:11Z`; `n=200`, `seed=7`, `campaigns_sha256 78ebccbe...f296ef537`.
  - The other two steps (`require_provenance_ci`, `require_two_approvals`) show 167 before and after.
- **Command:** `uv run python -m redteam.harden --n 200 --seed 7 --case xz` (`make harden CASE=xz`, `.\make.ps1 harden`). Code: `redteam/harden.py`.
- **Where 152 is quoted:**
  - `README.md:111`
  - `docs/blog/post.md:59`
  - (the JSON itself, `eval/results/hardening_redteam_xz.json:59`)
  - Unrelated "152" matches in `reader_full_run.json:1030`, `redteam_xz.json:14617`, `redteam_tallowdate.json:14693`.
- **Rerun value:** `add_second_keeper` caught **152** of 200 (167 before), so it **equals 152**. The number reproduces.
  - Run on port 6380 via `run_hardening("xz", 200, 7)` from a scratch script (started 22:19, took over an hour), writing to `docs/research/harden_rerun_6380.json` so no file in `eval/results/` is touched.
  - Same `campaigns_sha256` (`78ebccbe...f296ef537`), same real-graph counts before and after (4679 nodes / 4668 edges; unchanged).
  - Other fields match too: missed 48, caught_rate 0.76, median_lead_time_days 1.1416670000000004, guardians 1 to 2, takeover cost unchanged. The other two steps stay at 167.
  - No cause to look for, since nothing differs. The README and blog already say the build does not explain the drop; this rerun does not explain it either.
  - Not rerun: port 6390 (my first attempt there was killed before finishing).
