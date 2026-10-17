# Team Integration Status Report

**Agent:** Agent 4 (Demo, Pitch, Merge Lead)  
**Branch:** `team/integration`  
**Date:** October 18, 2026  

---

## 1. Merged Branches and Commit Hashes

- **Merged Branch:** `team/t1-slack`
  - **Merge Commit:** `7a79410ca8dca1ba65724fff22e011c825c9a586` (`Merge branch 'team/t1-slack' into team/integration`)
  - **Fix Commit for Slack Token Env:** `ce23756ffe00e07f8d3af61365af011cb9fc1556` (`fix(slack): load dotenv at module level so test monkeypatching functions properly`)
- **Current Integration Head:** `9ddc64e60ee3871c91901bac8b5f77cd5220bd9f` (incorporating `team/t1-slack`, `team/t4-demo`, and `team/t3-detect`)

---

## 2. Test Suite Counts

Full repository test execution on branch `team/integration` (`uv run pytest`):
- **Total Test Items:** 1,063
- **Passed:** 1,059
- **Strict Expected XFail:** 1 (`tests/integration/test_smoke_algos.py::test_sspaths_weighted_expectation`)
- **Failed:** 3 (1 persistent regression + 2 transient graph-list collisions during full suite run)
- **Skipped:** 0

### Test Breakdown by Subsystem:
- **Slack App (`team/t1-slack`):**
  - `tests/unit/test_slack_client.py`: 22 passed / 0 failed
  - `tests/unit/test_slack_listener.py`: 11 passed / 0 failed
  - `tests/unit/test_slack_notify.py`: 17 passed / 0 failed
  - `tests/unit/test_slack_inbox_api.py`: 19 passed / 0 failed
  - `tests/unit/test_slack_no_accusation.py`: 22 passed / 0 failed
  - `tests/unit/test_slack_render.py`: 10 passed / 0 failed
  - **Total Slack Tests:** 101 passed / 0 failed
- **Custody Memory & Demo (`team/t4-demo`):**
  - `tests/unit/test_custody.py`: 3 passed / 0 failed
  - `tests/integration/test_custody_demo.py`: 4 passed / 0 failed
- **Detectors (`team/t3-detect`):**
  - `tests/unit/test_t3_detectors.py`: 13 passed / 0 failed
  - `tests/integration/test_detectors.py`: 41 passed / 0 failed
  - `tests/integration/test_pressure_vouch.py`: 22 passed / 0 failed
- **Boundary & Governance:**
  - `tests/unit/test_boundary.py`: 59 passed / 0 failed

---

## 3. Test Failures & Analysis

As required by integration policy, execution stopped upon detection of test failures and no test expectations were modified.

### 1. `tests/integration/test_takeover.py::test_scratch_graph_is_deleted_after_a_failed_query`
- **Error:** `Failed: DID NOT RAISE ResponseError` at line 151.
- **Root Cause:**
  In commit `7e940c0` (`team/t3-detect`), `core/takeover/guardians.py` was modified to wrap `client.query(scratch, GUARDIANS_QUERY, params, timeout_ms=timeout_ms)` in a `try...except ResponseError:` block that returns `res.status = NOT_COMPUTED` rather than letting `ResponseError` propagate.
  However, `test_takeover.py:151` intentionally monkeypatches an invalid Cypher query and asserts `with pytest.raises(ResponseError): gmod.guardians(...)` to verify that scratch graph cleanup succeeds even when queries fail.
- **Resolution Path:** In `core/detectors/lone_keeper.py`, catch `ResponseError` from `gmod.guardians()` around the caller rather than swallowing it inside `core/takeover/guardians.py`, preserving `guardians.py` contract.

### 2. Transient Graph List Collisions in Full Suite:
- `tests/integration/test_ablation_memory.py::test_the_real_graph_is_unchanged_and_nothing_is_left_behind`
- `tests/integration/test_incidents_replay.py::test_a_replay_writes_nothing_and_leaves_no_copy`
- **Root Cause:** Both assertions inspect global FalkorDB `GRAPH.LIST` to ensure their own runs left no temporary graphs. When run concurrently or following a crashed test that left temporary graphs in FalkorDB before cleanup, extra graph names were detected. When run sequentially in isolation (`uv run pytest tests/integration/test_ablation_memory.py tests/integration/test_incidents_replay.py`), both pass 100% (6/6 and 4/4).

---

## 4. Open Items

- `real Slack click test needs a public URL (tunnel or hosting).`
