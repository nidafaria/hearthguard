"""Integration tests for custody flow (Day 1 write, app closed, Day 4 recall).

Tests run on a scratch org graph against the real FalkorDB container (port 6413).
Verifies:
1. Day 1 write persists into the graph.
2. Fresh client (app closed / reopened) recalls Day 1 baseline at Day 4.
3. Action Boundary (§4.4) strictly forbids automatic blocking.
4. Hearthguard WARNS with a private note (Level 1) and suggests a safety step (Level 2).
5. demo.custody_demo runs end-to-end and exits 0.
"""

import pytest

from core.graph.client import FalkorClient
from core.memory.custody import (
    evaluate_custody_action,
    has_custody,
    recall_custody_baseline,
    record_custody_baseline,
)
from demo.custody_demo import run_demo
from tests.integration.scratch_graphs import drop_owned, new_org_id, owned

pytestmark = pytest.mark.usefixtures("real_graphs_untouched")

DAY_1_T = 1_700_000_000
DAY_4_T = 1_700_259_200


@pytest.fixture
def org_graph():
    client = FalkorClient()
    oid = new_org_id()
    graph = f"org_{oid}"
    assert owned(graph)
    yield client, graph
    drop_owned(client, oid)


def test_custody_day1_write_and_day4_recall_across_sessions(org_graph):
    client_day1, graph = org_graph

    # Day 1: Write custody baseline
    record_custody_baseline(
        client_day1,
        graph=graph,
        custodian_hid="act_alice_01",
        custodian_name="Alice",
        privilege="release",
        at=DAY_1_T,
    )

    # Simulate app closed: destroy client instance
    del client_day1

    # Day 4: New app instance connects to persistent graph
    client_day4 = FalkorClient()

    # Recall custody baseline
    custodians = recall_custody_baseline(client_day4, graph, privilege="release", as_of_t=DAY_4_T)
    assert len(custodians) == 1
    assert custodians[0]["hid"] == "act_alice_01"
    assert custodians[0]["name"] == "Alice"
    assert custodians[0]["granted_at"] == DAY_1_T

    # Alice has custody
    assert has_custody(client_day4, graph, "act_alice_01", privilege="release", as_of_t=DAY_4_T)

    # Outsider Mallory does NOT have custody
    assert not has_custody(
        client_day4, graph, "act_mallory_99", privilege="release", as_of_t=DAY_4_T
    )


def test_custody_evaluation_warns_and_never_blocks(org_graph):
    client, graph = org_graph

    # Day 1 write
    record_custody_baseline(
        client,
        graph=graph,
        custodian_hid="act_alice_01",
        custodian_name="Alice",
        privilege="release",
        at=DAY_1_T,
    )

    # Day 4: Mallory attempts release
    eval_result = evaluate_custody_action(
        client,
        graph=graph,
        actor_hid="act_mallory_99",
        actor_name="Mallory",
        action_kind="release",
        at=DAY_4_T,
    )

    assert not eval_result.has_custody
    assert not eval_result.blocked  # NEVER automatically blocks!
    assert "refused" in (eval_result.boundary_refusal or "")
    assert eval_result.boundary_level == 1  # Level 1 Private Note
    assert "Alice" in eval_result.warning_note
    assert "Mallory" in eval_result.warning_note
    assert eval_result.warning_note.endswith("?")
    assert eval_result.suggested_step is not None
    assert "Verify" in eval_result.suggested_step


def test_custody_evaluation_allows_legitimate_custodian(org_graph):
    client, graph = org_graph

    # Day 1 write
    record_custody_baseline(
        client,
        graph=graph,
        custodian_hid="act_alice_01",
        custodian_name="Alice",
        privilege="release",
        at=DAY_1_T,
    )

    # Alice performs release on Day 4
    eval_result = evaluate_custody_action(
        client,
        graph=graph,
        actor_hid="act_alice_01",
        actor_name="Alice",
        action_kind="release",
        at=DAY_4_T,
    )

    assert eval_result.has_custody
    assert not eval_result.blocked
    assert eval_result.boundary_level == 0
    assert eval_result.warning_note is None
    assert eval_result.suggested_step is None


def test_custody_demo_runs_end_to_end_on_scratch_graph():
    oid = new_org_id()
    graph = f"org_{oid}"
    client = FalkorClient()
    try:
        rc = run_demo(graph_name=graph, cleanup=True)
        assert rc == 0
    finally:
        drop_owned(client, oid)
