"""Owner memory (docs/HEARTHGUARD.md 9): a dismissed situation does not return without new evidence.

Runs on a scratch org (tests/integration/scratch_graphs.py). The rows are hand-made and
synthetic: one fired move, the same in two quarters.
"""

import dataclasses

import pytest

from core.agents import inbox_graph as ig
from core.agents.cases import CASES, RESULTS
from core.graph.client import FalkorClient
from tests.integration.scratch_graphs import drop_owned, new_org_id, owned

pytestmark = pytest.mark.usefixtures("real_graphs_untouched")

DAY = 86_400
T1 = 1_700_000_000
T2 = T1 + 90 * DAY


def _row(quarter: str, T: int, pressure: str = "FIRED") -> dict:
    return {
        "quarter": quarter,
        "T": T,
        "T_iso": "",
        "decision": "NOTE",
        "moves": {
            "PRESSURE": pressure,
            "VOUCH": "NOT_FIRED",
            "RUSH": "NOT_FIRED",
            "BYPASS": "NOT_FIRED",
        },
        "lone_keeper": "FLAG_SET",
        "reasons": {},
        "detail": {},
        "hold_reason": None,
    }


@pytest.fixture
def org():
    client = FalkorClient()
    oid = new_org_id()
    assert owned(f"org_{oid}")
    yield oid
    drop_owned(client, oid)


@pytest.fixture
def case(org):
    return dataclasses.replace(CASES["tallowdate"], org=org)


def _status(client, case, quarter):
    r = client.query(
        case.graph,
        "MATCH (f:Finding {id: $fid}) RETURN f.status, f.remembered",
        {"fid": ig.finding_id(case, quarter)},
        timeout_ms=10_000,
    )
    return r.result_set[0]


def test_a_dismissed_situation_is_held_back_in_a_later_quarter(org, case):
    client = FalkorClient()
    ig.sync_case(client, case, [_row("2021-Q1", T1)], RESULTS, lambda: T1)
    ig.record_dismissal(client, case, "2021-Q1", "these are our CI bots", T1 + DAY)
    out = ig.sync_case(
        client, case, [_row("2021-Q1", T1), _row("2021-Q2", T2)], RESULTS, lambda: T2
    )
    assert out["remembered"] == 1
    assert _status(client, case, "2021-Q2") == ["dismissed", True]


def test_new_evidence_after_the_dismissal_brings_the_situation_back(org, case):
    client = FalkorClient()
    rows = [_row("2021-Q1", T1), _row("2021-Q2", T2)]
    ig.sync_case(client, case, rows[:1], RESULTS, lambda: T1)
    ig.record_dismissal(client, case, "2021-Q1", "these are our CI bots", T1 + DAY)
    ig.sync_case(client, case, rows, RESULTS, lambda: T2)
    assert _status(client, case, "2021-Q2")[0] == "dismissed"
    client.query(
        case.graph,
        "CREATE (:Claim {id: 'tst-new-evidence', kind: 'PRESSURE', at: $at, synthetic: true})",
        {"at": T1 + 10 * DAY},
        timeout_ms=10_000,
    )
    out = ig.sync_case(client, case, rows, RESULTS, lambda: T2)
    assert out["remembered"] == 0
    assert _status(client, case, "2021-Q2") == ["open", False]


def test_a_different_situation_is_not_held_back(org, case):
    client = FalkorClient()
    ig.sync_case(client, case, [_row("2021-Q1", T1)], RESULTS, lambda: T1)
    ig.record_dismissal(client, case, "2021-Q1", "these are our CI bots", T1 + DAY)
    later = _row("2021-Q2", T2, pressure="NOT_COMPUTED")  # a move the owner did not dismiss
    ig.sync_case(client, case, [_row("2021-Q1", T1), later], RESULTS, lambda: T2)
    assert _status(client, case, "2021-Q2")[0] == "open"


def test_a_later_dismissal_does_not_hold_back_an_earlier_quarter(org, case):
    client = FalkorClient()
    rows = [_row("2021-Q1", T1), _row("2021-Q2", T2)]
    ig.sync_case(client, case, rows, RESULTS, lambda: T2)
    ig.record_dismissal(client, case, "2021-Q2", "these are our CI bots", T2 + DAY)
    out = ig.sync_case(client, case, rows, RESULTS, lambda: T2)
    assert out["remembered"] == 0
    assert _status(client, case, "2021-Q1")[0] == "open"
