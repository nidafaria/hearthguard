"""Pressure and Vouch on hand-built graphs, and the claim writer. Real FalkorDB, no mocks.

Times are day numbers * 86400 s. Thresholds are the frozen ones in config/frozen.yaml: Pressure
window 120 days, >= 3 claims from >= 2 low-history actors (history < 90 days or < 5 actions);
Vouch >= 2 low-history vouchers for one candidate, a SHARES component with >= 2 signal types.
Nothing here is a finding about any real project.
"""

import pytest

from core.claims import graph_write
from core.detectors import pressure, vouch
from core.detectors.common import FIRED, NOT_COMPUTED, NOT_FIRED
from core.graph.client import FalkorClient
from core.takeover import scratch as sc

DAY = 86_400
T_DAY = 1000
T = T_DAY * DAY


@pytest.fixture(scope="module")
def client() -> FalkorClient:
    return FalkorClient()


@pytest.fixture
def org(client, request):
    org = "pv_" + request.node.name.split("[")[0].removeprefix("test_")[:30]
    client.drop(sc.graph_for(org))
    yield org
    client.drop(sc.graph_for(org))


def actor(client, org, hid, seen_day=None, actions=0):
    g = sc.graph_for(org)
    props = "{hid: $hid, kind: 'human'}"
    client.query(
        g,
        f"MERGE (a:Actor {props}) SET a.first_seen_in_org = $seen",
        {"hid": hid, "seen": None if seen_day is None else seen_day * DAY},
    )
    for i in range(actions):
        client.query(
            g,
            "MATCH (a:Actor {hid: $hid}) CREATE (a)-[d:DID]->(:Action {kind: 'commit', ref: $ref}) "
            "SET d.at = $at",
            {"hid": hid, "ref": f"{hid}-{i}", "at": (seen_day or 0) * DAY + i},
        )


def claim(client, org, hid, kind, day, n, target=None):
    client.query(
        sc.graph_for(org),
        "MATCH (a:Actor {hid: $hid}) CREATE (a)-[:ASSERTED]->"
        "(:Claim {id: $id, kind: $kind, at: $at, target_hid: $target})",
        {"hid": hid, "id": f"c{n}", "kind": kind, "at": day * DAY, "target": target},
    )


def shares(client, org, a, b, signal):
    client.query(
        sc.graph_for(org),
        "MATCH (a:Actor {hid: $a}), (b:Actor {hid: $b}) CREATE (a)-[:SHARES {signal: $s}]->(b)",
        {"a": a, "b": b, "s": signal},
    )


def low_pair(client, org):
    actor(client, org, "A", seen_day=990)  # 10 days of history, 0 actions: low
    actor(client, org, "B", seen_day=995)  # 5 days of history: low


# ------------------------------------------------------------------ Pressure
# Window: (880, 1000] days. A, B low-history.
def test_pressure_three_claims_from_two_low_actors_leaves_keeper_condition_open(client, org):
    # A@950 + B@960 + B@970 = 3 claims, 2 actors -> condition (1) holds.
    # Condition (2) is open in the freeze -> NOT_COMPUTED with that reason.
    low_pair(client, org)
    claim(client, org, "A", "PRESSURE", 950, 1)
    claim(client, org, "B", "URGENCY", 960, 2)
    claim(client, org, "B", "PRESSURE", 970, 3)
    res = pressure.pressure(client, org, T)
    assert res.status == NOT_COMPUTED
    assert res.reason == "keeper activity condition open in freeze"
    assert res.evidence["claims_by_low_history_actors"] == 3
    assert res.evidence["low_history_actors"] == 2
    assert res.evidence["claim_condition_met"] is True
    assert res.queries and res.query_ms is not None


def test_pressure_three_claims_from_one_actor_does_not_fire(client, org):
    # A@950, A@960, A@970 = 3 claims, 1 actor -> (1) fails -> NOT_FIRED.
    low_pair(client, org)
    for n, d in enumerate((950, 960, 970), start=1):
        claim(client, org, "A", "PRESSURE", d, n)
    res = pressure.pressure(client, org, T)
    assert res.status == NOT_FIRED
    assert res.evidence["low_history_actors"] == 1


def test_pressure_claim_older_than_120_days_is_outside_the_window(client, org):
    # A@950, A@960 in window; B@880 is exactly at the window start (880 > 880 is false) -> out.
    # 2 claims in window -> NOT_FIRED.
    low_pair(client, org)
    claim(client, org, "A", "PRESSURE", 950, 1)
    claim(client, org, "A", "PRESSURE", 960, 2)
    claim(client, org, "B", "PRESSURE", 880, 3)
    res = pressure.pressure(client, org, T)
    assert res.status == NOT_FIRED and res.evidence["claims_in_window"] == 2


def test_pressure_established_actors_do_not_count_as_low_history(client, org):
    # E: first seen day 0, 5 actions -> 1000 days and 5 actions: not low.
    # Claims: A@950 (low), E@951, E@952, E@953 -> only 1 claim by low actors -> NOT_FIRED.
    low_pair(client, org)
    actor(client, org, "E", seen_day=0, actions=5)
    claim(client, org, "A", "PRESSURE", 950, 1)
    for n, d in enumerate((951, 952, 953), start=2):
        claim(client, org, "E", "PRESSURE", d, n)
    res = pressure.pressure(client, org, T)
    assert res.status == NOT_FIRED
    assert (res.evidence["claims_in_window"], res.evidence["claims_by_low_history_actors"]) == (
        4,
        1,
    )


def test_pressure_an_actor_with_few_actions_is_low_even_if_old(client, org):
    # F: first seen day 0 (1000 days) but only 4 actions (< 5) -> low. F@950, B@960, B@970 -> fires
    # condition (1) -> NOT_COMPUTED (keeper condition open).
    actor(client, org, "F", seen_day=0, actions=4)
    actor(client, org, "B", seen_day=995)
    claim(client, org, "F", "PRESSURE", 950, 1)
    claim(client, org, "B", "PRESSURE", 960, 2)
    claim(client, org, "B", "PRESSURE", 970, 3)
    assert pressure.pressure(client, org, T).status == NOT_COMPUTED


def test_pressure_a_later_claim_changes_the_answer_only_once_T_reaches_it(client, org):
    # A@950, B@960 and B@1001. At T=1000 days: 2 claims -> NOT_FIRED.
    # At T=1002 days: 3 claims from 2 actors -> condition (1) holds -> NOT_COMPUTED.
    low_pair(client, org)
    claim(client, org, "A", "PRESSURE", 950, 1)
    claim(client, org, "B", "PRESSURE", 960, 2)
    claim(client, org, "B", "PRESSURE", 1001, 3)
    assert pressure.pressure(client, org, T).status == NOT_FIRED
    assert pressure.pressure(client, org, 1002 * DAY).status == NOT_COMPUTED


def test_pressure_other_claim_kinds_are_ignored(client, org):
    # Only PRESSURE and URGENCY count: A PRESSURE, B CAPACITY, B PRESSURE = 2 -> NOT_FIRED.
    low_pair(client, org)
    claim(client, org, "A", "PRESSURE", 950, 1)
    claim(client, org, "B", "CAPACITY_STATEMENT", 960, 2)
    claim(client, org, "B", "PRESSURE", 970, 3)
    assert pressure.pressure(client, org, T).status == NOT_FIRED


def test_pressure_actor_with_no_first_seen_and_no_action_is_not_computed(client, org):
    actor(client, org, "A")  # no first_seen_in_org and no action
    actor(client, org, "B", seen_day=995)
    claim(client, org, "A", "PRESSURE", 950, 1)
    res = pressure.pressure(client, org, T)
    assert res.status == NOT_COMPUTED and "first-seen" in res.reason


def test_pressure_no_claims_at_all_is_not_fired(client, org):
    low_pair(client, org)
    assert pressure.pressure(client, org, T).status == NOT_FIRED


# ------------------------------------------------------------------ Vouch
def test_vouch_no_vouch_claims_is_not_fired(client, org):
    low_pair(client, org)
    res = vouch.vouch(client, org, T)
    assert res.status == NOT_FIRED and "0 low-history" in res.reason


def test_vouch_established_vouchers_do_not_count(client, org):
    actor(client, org, "E1", seen_day=0, actions=6)
    actor(client, org, "E2", seen_day=0, actions=6)
    claim(client, org, "E1", "VOUCH", 900, 1, target="C")
    claim(client, org, "E2", "VOUCH", 900, 2, target="C")
    assert vouch.vouch(client, org, T).status == NOT_FIRED


def test_vouch_without_a_target_cannot_establish_the_same_candidate(client, org):
    low_pair(client, org)
    claim(client, org, "A", "VOUCH", 900, 1)
    claim(client, org, "B", "VOUCH", 910, 2)
    res = vouch.vouch(client, org, T)
    assert res.status == NOT_COMPUTED and "no target" in res.reason


def test_vouch_two_vouchers_for_one_candidate_without_shares_is_not_computed(client, org):
    low_pair(client, org)
    claim(client, org, "A", "VOUCH", 900, 1, target="C")
    claim(client, org, "B", "VOUCH", 910, 2, target="C")
    res = vouch.vouch(client, org, T)
    assert res.status == NOT_COMPUTED and "no SHARES edges" in res.reason


def test_vouch_fires_with_two_vouchers_one_component_two_signal_types(client, org):
    # A and B vouch for C. SHARES A-B with creation_window and domain_hash: one component of
    # size 2 with 2 signal types -> FIRED.
    low_pair(client, org)
    claim(client, org, "A", "VOUCH", 900, 1, target="C")
    claim(client, org, "B", "VOUCH", 910, 2, target="C")
    shares(client, org, "A", "B", "creation_window")
    shares(client, org, "A", "B", "domain_hash")
    res = vouch.vouch(client, org, T)
    assert res.status == FIRED
    assert res.evidence["component_size"] == 2
    assert res.evidence["signal_types"] == ["creation_window", "domain_hash"]


def test_vouch_one_signal_type_is_not_enough(client, org):
    low_pair(client, org)
    claim(client, org, "A", "VOUCH", 900, 1, target="C")
    claim(client, org, "B", "VOUCH", 910, 2, target="C")
    shares(client, org, "A", "B", "creation_window")
    assert vouch.vouch(client, org, T).status == NOT_FIRED


def test_vouch_different_candidates_do_not_count_together(client, org):
    low_pair(client, org)
    claim(client, org, "A", "VOUCH", 900, 1, target="C")
    claim(client, org, "B", "VOUCH", 910, 2, target="D")
    shares(client, org, "A", "B", "creation_window")
    shares(client, org, "A", "B", "domain_hash")
    res = vouch.vouch(client, org, T)
    assert res.status == NOT_FIRED and "no candidate" in res.reason


def test_vouch_vouchers_in_different_components_do_not_fire(client, org):
    # A, B vouch for C but have no SHARES between them; A-X and B-Y share signals instead.
    # No SHARES edge joins two vouchers, so none is read between them -> NOT_COMPUTED.
    low_pair(client, org)
    actor(client, org, "X", seen_day=990)
    actor(client, org, "Y", seen_day=990)
    claim(client, org, "A", "VOUCH", 900, 1, target="C")
    claim(client, org, "B", "VOUCH", 910, 2, target="C")
    shares(client, org, "A", "X", "creation_window")
    shares(client, org, "B", "Y", "domain_hash")
    assert vouch.vouch(client, org, T).status == NOT_COMPUTED


def test_vouch_a_future_claim_is_ignored(client, org):
    low_pair(client, org)
    claim(client, org, "A", "VOUCH", 900, 1, target="C")
    claim(client, org, "B", "VOUCH", 1005, 2, target="C")
    assert vouch.vouch(client, org, T).status == NOT_FIRED


# ------------------------------------------------------------------ claim writer
ENTRIES = [
    {
        "message_id": "msg00001",
        "date_utc": "2022-03-01T10:00:00Z",
        "author_hash": "h1",
        "claims": [{"kind": "PRESSURE", "quote": "hurry up", "offset": 5, "confidence": 0.8}],
    },
    {
        "message_id": "msg00002",
        "date_utc": None,
        "author_hash": "h2",
        "claims": [{"kind": "VOUCH", "quote": "I trust", "offset": 0, "confidence": 0.5}],
    },
    {
        "message_id": "msg00003",
        "date_utc": "2022-03-02T00:00:00Z",
        "author_hash": None,
        "claims": [{"kind": "URGENCY", "quote": "now", "offset": 0, "confidence": 0.5}],
    },
    {
        "message_id": "msg00004",
        "date_utc": "2022-03-02T00:00:00Z",
        "author_hash": "h3",
        "claims": [],
    },
]


def counts(client, org):
    r = client.query(sc.graph_for(org), "MATCH (n) RETURN labels(n)[0], count(n)").result_set
    e = client.query(sc.graph_for(org), "MATCH ()-[r]->() RETURN type(r), count(r)").result_set
    return dict(r), dict(e)


def test_claim_writer_writes_a_dated_claim_and_reports_what_it_left_out(client, org):
    out = graph_write.write_claims(client, sc.graph_for(org), ENTRIES)
    assert out == {"claims_written": 1, "left_out": {"no_date": 1, "no_author": 1}}
    nodes, edges = counts(client, org)
    assert nodes["Claim"] == 1 and nodes["Actor"] == 1 and nodes["Span"] == 1
    assert edges["ASSERTED"] == 1 and edges["FROM"] == 1 and edges["HAS"] == 1


def test_claim_writer_is_idempotent(client, org):
    graph_write.write_claims(client, sc.graph_for(org), ENTRIES)
    first = counts(client, org)
    graph_write.write_claims(client, sc.graph_for(org), ENTRIES)
    assert counts(client, org) == first


def test_claim_writer_leaves_an_existing_actor_untouched(client, org):
    actor(client, org, "h1", seen_day=10, actions=2)
    graph_write.write_claims(client, sc.graph_for(org), ENTRIES)
    row = client.query(
        sc.graph_for(org), "MATCH (a:Actor {hid: 'h1'}) RETURN a.first_seen_in_org, a.source"
    ).result_set[0]
    assert row == [10 * DAY, None]


def test_a_new_mail_actor_is_marked_and_first_seen_is_the_first_claim(client, org):
    graph_write.write_claims(client, sc.graph_for(org), ENTRIES)
    row = client.query(
        sc.graph_for(org), "MATCH (a:Actor {hid: 'h1'}) RETURN a.first_seen_in_org, a.source"
    ).result_set[0]
    assert row == [graph_write.to_epoch("2022-03-01T10:00:00Z"), "mail"]
