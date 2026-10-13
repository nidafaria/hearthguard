"""Northbridge / Kestrel case on a real FalkorDB (spec §11.1), through the finance pack.

Hand-worked expectations (dataset in packs/finance/synthetic.py):
  - Daniel's first action is Aug 4 10:00, his change rights come Sep 15 11:00: 42 days + 1 hour.
    The six earlier grants took 150, 165, 180, 190, 200, 210 days. n = 6 so the org p10 applies:
    h = 5 * 0.10 = 0.5 -> 150 + 0.5 * (165 - 150) = 157.5 days. 42.04 < 157.5, so Rush fires.
  - Earlier bank changes all: portal, callback true, 2 approvers. The Sep 17 one: email, no
    callback, 1 approver. All three properties differ, so Bypass fires on exactly those three.
  - Before the leave (Sep 7) two holders can approve at 2 approvals each: guardians 2, cost 2.
    On Sep 17 the controller is away: guardians 1, cost min(2, 1 available) = 1.
  - Requiring two approvals on a copy turns the cost from 1 to 2, guardians stay 1.
"""

import uuid

import pytest

from core.graph.client import FalkorClient
from eval import northbridge_case as nc
from packs.finance import mapping, parse


@pytest.fixture(scope="module")
def result():
    client = FalkorClient()
    org = "nb" + uuid.uuid4().hex[:8]
    try:
        yield nc.run(client, org)
    finally:
        client.drop(f"org_{org}")


def test_rush_fires_on_the_planted_contact_and_not_on_a_normal_one(result):
    rush = result["moves"]["rush"]
    assert rush["status"] == "FIRED"
    assert rush["evidence"]["rule"] == "org_p10"
    assert rush["evidence"]["threshold_days"] == 157.5
    assert round(rush["evidence"]["days"], 2) == 42.04
    assert result["controls"]["rush_on_a_normal_contact"]["status"] == "NOT_FIRED"


def test_bypass_fires_on_all_three_properties_and_not_on_a_normal_change(result):
    bp = result["moves"]["bypass"]
    assert bp["status"] == "FIRED"
    assert bp["evidence"]["differing"] == ["channel", "callback", "approvers"]
    assert result["controls"]["bypass_on_a_normal_bank_change"]["status"] == "NOT_FIRED"


def test_lone_keeper_flag_is_set_by_guardians(result):
    lk = result["moves"]["lone_keeper"]
    assert lk["status"] == "FLAG_SET"
    assert lk["evidence"]["guardians_is_1"] is True


def test_pressure_and_vouch_are_reported_not_computed_not_faked(result):
    for name in ("pressure", "vouch"):
        assert result["moves"][name]["status"] == "NOT COMPUTED"


def test_guardians_and_cost_before_and_after_the_leave(result):
    assert (result["before_leave"]["guardians"], result["before_leave"]["takeover_cost"]) == (2, 2)
    assert (result["at_case"]["guardians"], result["at_case"]["takeover_cost"]) == (1, 1)


def test_restoring_two_person_approval_raises_the_cost_from_1_to_2(result):
    h = result["hardening"]
    assert h["before"]["takeover_cost"] == 1
    assert h["after"]["takeover_cost"] == 2
    assert h["after"]["guardians"] == 1


def test_hardening_ran_on_a_copy_and_left_the_org_graph_alone(result):
    assert (
        result["org_graph_edge_count_before_hardening"]
        == result["org_graph_edge_count_after_hardening"]
    )


def test_a_second_load_changes_no_count():
    client = FalkorClient()
    org = "nb" + uuid.uuid4().hex[:8]
    g = f"org_{org}"
    parsed = parse.parse_records(nc.load_dataset(), parse.default_salt())
    try:
        mapping.load(client, g, parsed, nc.T_CASE, org)
        n1 = client.query(g, "MATCH (n) RETURN count(n)", timeout_ms=30_000).result_set[0][0]
        e1 = client.query(g, "MATCH ()-[r]->() RETURN count(r)", timeout_ms=30_000).result_set[0][0]
        mapping.load(client, g, parsed, nc.T_CASE, org)
        n2 = client.query(g, "MATCH (n) RETURN count(n)", timeout_ms=30_000).result_set[0][0]
        e2 = client.query(g, "MATCH ()-[r]->() RETURN count(r)", timeout_ms=30_000).result_set[0][0]
        assert (n1, e1) == (n2, e2)
    finally:
        client.drop(g)
