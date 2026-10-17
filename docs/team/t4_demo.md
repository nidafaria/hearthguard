# Team 4 Status: Custody Memory Flow, Demo & Memory-Led Pitch

**Agent:** Agent 4 (Custody Demo, Pitch & Final Merge Lead)  
**Branch:** `team/t4-demo`  
**Date:** October 18, 2026  

---

## 1. Summary of Work Done

### Custody Memory Flow (`core/memory/custody.py`)
- **Lifecycle Implementation:**
  - **Day 1 Write:** `record_custody_baseline()` persists maintainer custody (`Actor {hid, name}`, `Privilege {kind}`, `CustodyRecord {id, at, privilege, status}`) and `:GRANTED` / `:HOLDS_CUSTODY` edges in FalkorDB using idempotent `MERGE` on unique keys (§6.6).
  - **App Closed:** Process terminates; zero state retained in Python memory; all persistence resides in FalkorDB.
  - **Day 4 Recall:** `recall_custody_baseline()` and `has_custody()` query persistent graph memory as of Day 4 ($T_4$), recalling Day 1 custodians across independent application sessions.
- **Action Boundary (§4.4) Enforcement:**
  - `evaluate_custody_action()` verifies that Hearthguard **never** automatically blocks releases or payments (`block_release_or_payment` strictly refused with `BoundaryViolation('never')`).
  - Instead, Hearthguard **WARNS and RECALLS**:
    - **Level 1 (Private Note):** Emits a private note to the person in charge (owner), phrased as an evidenced question comparing Day 4 attempted action against recalled Day 1 custody.
    - **Level 2 (Safety Step):** Suggests concrete out-of-band verification before signing or publishing.

### Screen-Recording Demo (`demo/custody_demo.py`)
- Self-contained, runnable script: `uv run python -m demo.custody_demo`
- Produces clean, structured, terminal-formatted output designed for screen recording.
- Clearly demonstrates Step 1 (Day 1 Write), Step 2 (App Closed / RAM flush), Step 3 (Day 4 Recall & Action Boundary Enforcement: Refuses Block, Recalls Baseline, Warns with Note).

### Test Suite (`tests/unit/test_custody.py`, `tests/integration/test_custody_demo.py`)
- Added 7 comprehensive tests:
  - Deterministic unique custody record IDs.
  - Action Boundary strict refusal of automatic blocking (`rule == 'never'`).
  - Action Boundary allowance of Level 1 private note and Level 2 safety step.
  - Real FalkorDB scratch-graph integration test verifying Day 1 write and Day 4 recall across fresh client instances.
  - Custody evaluation verifying outsider triggers warning note without blocking.
  - Custody evaluation verifying legitimate custodian passes at Level 0.
  - End-to-end execution of `demo.custody_demo.run_demo()` on a scratch graph.
- All 7 tests pass in 1.38s.

### README & Pitch Update (`README.md`)
- Rewrote the top section and one-line pitch so **memory leads, not security**:
  `> Persistent graph memory for software projects on FalkorDB: remembering custodians, handoffs, and normal across sessions.`
- Accurately claims only what the code does:
  - Per-project graph names (`org_<id>`, `ecosystem_<id>`).
  - Agent handoffs through graph state on the task board.
  - Custody flow across sessions: warns and recalls, never blocks (§4.4).
- Passed all README verification checks in `tests/integration/test_incidents_readme.py`.

---

## 2. Test Counts

- `tests/unit/test_custody.py`: **3 passed**
- `tests/integration/test_custody_demo.py`: **4 passed**
- **Total Custody Suite:** **7 passed / 0 failed**
- Static boundary scan (`tests/unit/test_boundary.py`): **59 passed / 0 failed**
- README verification (`tests/integration/test_incidents_readme.py`): **5 passed / 0 failed**
- Overall repository test suite: **1,017 passed, 1 xfailed** (with cached fixtures).
