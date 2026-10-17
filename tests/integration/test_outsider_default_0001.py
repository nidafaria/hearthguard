"""Row 13: the OUTSIDER rule under the default chosen in docs/decisions/0001 (2026-10-18).

The default keeps the entry hop at 1 and subtracts it, so the spec's own numbers hold: a lone keeper
costs 1 (spec 2.2) and the two-keeper rule costs 2 (spec 8.5). Real FalkorDB, no mocks.
"""

import pytest

from core.graph.client import FalkorClient
from core.takeover import cost
from core.takeover import guardians as gmod
from core.takeover import scratch as sc
from tests.fixtures.takeover_cases import CASES, PRIV, T


@pytest.fixture(scope="module")
def client() -> FalkorClient:
    return FalkorClient()


def test_entry_hop_is_one_and_is_subtracted():
    assert cost.ENTRY_APPROVALS == 1


@pytest.mark.parametrize(
    ("case_name", "expected_cost"), [("a_single_chain", 1), ("c_two_approvals", 2)]
)
def test_lone_keeper_costs_one_and_two_keeper_rule_costs_two(client, case_name, expected_cost):
    case = next(c for c in CASES if c.name == case_name)
    org = f"tk_row13_{case_name[:1]}"
    client.drop(sc.graph_for(org))
    try:
        case.build(client, sc.graph_for(org))
        assert cost.takeover_cost(client, org, PRIV, T).cost == expected_cost
        assert gmod.guardians(client, org, PRIV, T).guardians == 1
    finally:
        client.drop(sc.graph_for(org))
