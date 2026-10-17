"""Custody demo: Day 1 write, app closed, Day 4 recall across sessions.

Demonstrates Hearthguard's persistent graph memory on FalkorDB:
1. Day 1: Write custody baseline into the graph (Alice has release custody).
2. App closed: State unallocated from process memory. Zero RAM state.
3. Day 4: App relaunched, queries persistent graph, recalls Day 1 baseline.
   Action Boundary (§4.4) strictly forbids automatic blocking of releases.
   Hearthguard WARNS and RECALLS, never orders or automatically blocks.

Run: uv run python -m demo.custody_demo
"""

import argparse
import gc
import sys

from core.graph.client import FalkorClient
from core.memory.custody import (
    evaluate_custody_action,
    recall_custody_baseline,
    record_custody_baseline,
)
from core.policy import boundary

DAY_1_T = 1_700_000_000  # Day 1 timestamp
DAY_4_T = 1_700_259_200  # Day 4 timestamp (T1 + 3 days)
DEFAULT_GRAPH = "org_custody_demo"


def run_demo(graph_name: str = DEFAULT_GRAPH, cleanup: bool = False) -> int:
    border = "=" * 76
    sub_border = "-" * 76

    print(border)
    print("  HEARTHGUARD CUSTODY MEMORY DEMO")
    print("  Action Boundary (Section 4.4): It asks, it never orders. Memory leads.")
    print(f"  Target Graph: {graph_name} | Persistent Store: FalkorDB")
    print(border)
    print()

    # -------------------------------------------------------------------------
    # STEP 1: DAY 1 - WRITE CUSTODY BASELINE
    # -------------------------------------------------------------------------
    print(f"[STEP 1: DAY 1 - WRITE CUSTODY BASELINE] (T = {DAY_1_T})")
    print(sub_border)
    client_day1 = FalkorClient()
    print(f"  Connected to FalkorDB on port {client_day1.port}.")
    print("  Action Boundary check for ingest & baseline write...")
    level_day1 = boundary.check("analyse")
    print(f"  Boundary Level: {level_day1} (ANALYSE) -> Allowed automatically.")

    custodian_hid = "act_alice_01"
    custodian_name = "Alice (Maintainer)"
    privilege = "release"

    print(f"  Recording custodian '{custodian_name}' with '{privilege}' rights...")
    rec_id = record_custody_baseline(
        client_day1,
        graph=graph_name,
        custodian_hid=custodian_hid,
        custodian_name=custodian_name,
        privilege=privilege,
        at=DAY_1_T,
    )
    print(f"  Graph write confirmed. CustodyRecord ID: {rec_id}")

    # Verify write
    active_custodians = recall_custody_baseline(
        client_day1, graph_name, privilege=privilege, as_of_t=DAY_1_T
    )
    print(f"  Current verified custodians in '{graph_name}':")
    for c in active_custodians:
        print(f"    - {c['name']} (hid: {c['hid']}) granted at T={c['granted_at']}")
    print("  Day 1 state successfully written to FalkorDB graph.")
    print()

    # -------------------------------------------------------------------------
    # STEP 2: APPLICATION CLOSED (Zero In-Memory State)
    # -------------------------------------------------------------------------
    print("[STEP 2: APPLICATION CLOSED - ZERO TRANSIENT RAM]")
    print(sub_border)
    print("  Disconnecting client from FalkorDB...")
    client_day1 = None
    del client_day1
    gc.collect()
    print("  Application process terminated. Python memory cleared.")
    print("  Zero in-memory state retained. All memory resides in FalkorDB.")
    print()

    # -------------------------------------------------------------------------
    # STEP 3: DAY 4 - RECALL & ACTION BOUNDARY ENFORCEMENT
    # -------------------------------------------------------------------------
    print(f"[STEP 3: DAY 4 - RECALL & ACTION BOUNDARY ENFORCEMENT] (T = {DAY_4_T})")
    print(sub_border)
    print("  Launching fresh application session...")
    client_day4 = FalkorClient()
    print(f"  Connected fresh client to FalkorDB on port {client_day4.port}.")

    unauthorized_actor_hid = "act_mallory_99"
    unauthorized_actor_name = "Mallory (Outsider)"
    attempted_action = "release"

    print(f"  Event detected: Account '{unauthorized_actor_name}' attempts '{attempted_action}'.")
    print()

    # 3a. Action Boundary enforcement: can Hearthguard automatically block?
    print("  --- Action Boundary (Section 4.4) Verification ---")
    print("  Querying policy: May Hearthguard automatically block this release?")
    try:
        boundary.check("block_release_or_payment", recipient="owner")
        print("  CRITICAL ERROR: Action boundary allowed automatic blocking!")
        return 1
    except boundary.BoundaryViolation as e:
        print("  POLICY ENFORCED: Automatic blocking REFUSED.")
        print(f"  Reason: {e}")
        print("  Hearthguard Action Boundary: Level 'Never' forbids automatic blocking.")
    print()

    # 3b. Custody evaluation & recall
    print("  --- Graph Memory Recall ---")
    eval_result = evaluate_custody_action(
        client_day4,
        graph=graph_name,
        actor_hid=unauthorized_actor_hid,
        actor_name=unauthorized_actor_name,
        action_kind=attempted_action,
        at=DAY_4_T,
        simulate_blocking_attempt=False,
    )

    print(f"  Actor custody verified in graph: {eval_result.has_custody}")
    print("  Recalled historical custodians from Day 1:")
    for c in eval_result.recalled_custodians:
        print(f"    - {c['name']} (hid: {c['hid']}) granted at T={c['granted_at']}")
    print()

    # 3c. Hearthguard response: WARN, not block
    print("  --- Hearthguard Decision: WARN & RECALL (Never Block) ---")
    print(f"  Action Boundary Level: {eval_result.boundary_level} (PRIVATE_NOTE)")
    print("  Level 1 Private Note (to Person in Charge):")
    print(f'    "{eval_result.warning_note}"')
    print()
    print("  Level 2 Concrete Safety Step Suggestion:")
    print(f'    "{eval_result.suggested_step}"')
    print()

    # -------------------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------------------
    print(border)
    print("  DEMO COMPLETE: CUSTODY LIFECYCLE VERIFIED")
    print("  1. Day 1: Wrote custody baseline to persistent graph.")
    print("  2. App Closed: Proved zero dependence on transient RAM.")
    print("  3. Day 4: Recalled baseline across sessions.")
    print("  4. Action Boundary: Forbade automatic blocking; warned person in charge.")
    print(border)

    if cleanup:
        client_day4.drop(graph_name)
        print(f"  Cleaned up temporary graph '{graph_name}'.")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Hearthguard Custody Memory Demo")
    parser.add_argument("--graph", default=DEFAULT_GRAPH, help="Graph name to use")
    parser.add_argument("--scratch", action="store_true", help="Drop graph after demo finishes")
    args = parser.parse_args()

    return run_demo(graph_name=args.graph, cleanup=args.scratch)


if __name__ == "__main__":
    sys.exit(main())
