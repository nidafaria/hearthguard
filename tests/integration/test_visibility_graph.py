"""Visibility graph (spec §6.1, §9) on a real FalkorDB: Place, PARTICIPATES_IN, RECORDED_IN.

Hand-worked expectations:
  - Finance (Northbridge, loaded at Sep 17): Daniel (lookalike domain) sent his first email to the
    AP inbox on Aug 4 10:00 and his last on Sep 17 09:00, so PARTICIPATES_IN(inbox) has
    since = 2025-08-04T10:00Z and last_at = 2025-09-17T09:00Z. He never posted in the chat channel.
  - Every Action loaded is RECORDED_IN exactly one Place.
  - Mail (two fake index rows by one author on the same list): since = the earlier date,
    last_at = the later, one edge, two RECORDED_IN edges, and a second run changes no count.
"""

import uuid

import pytest

from eval import northbridge_case as nc
from eval import populate_visibility as pv
from packs.finance import mapping, parse, synthetic


@pytest.fixture
def northbridge(client):
    org = "nb" + uuid.uuid4().hex[:8]
    g = f"org_{org}"
    parsed = parse.parse_records(nc.load_dataset(), parse.default_salt())
    mapping.load(client, g, parsed, nc.T_CASE, org)
    yield g
    client.drop(g)


def rows(client, g, cypher, params=None):
    return client.query(g, cypher, params, timeout_ms=30_000).result_set


def test_daniel_participates_in_the_inbox_from_aug_4_and_never_in_chat(client, northbridge):
    daniel = parse.hid(synthetic.DANIEL, parse.default_salt())
    got = rows(
        client,
        northbridge,
        "MATCH (:Actor {hid: $h})-[e:PARTICIPATES_IN]->(p:Place) "
        "RETURN p.ref, e.since, e.last_at ORDER BY p.ref",
        {"h": daniel},
    )
    since = parse.to_epoch("2025-08-04T10:00:00Z")
    last = parse.to_epoch("2025-09-17T09:00:00Z")
    portal_last = parse.to_epoch("2025-09-15T11:00:00Z")
    assert got == [
        ["northbridge:inbox:ap", since, last],
        ["northbridge:portal:vendors", portal_last, portal_last],
    ]


def test_every_action_is_recorded_in_exactly_one_place(client, northbridge):
    bad = rows(
        client,
        northbridge,
        "MATCH (x:Action) OPTIONAL MATCH (x)-[:RECORDED_IN]->(p:Place) "
        "WITH x, count(p) AS n WHERE n <> 1 RETURN count(x)",
    )
    assert bad == [[0]]


def test_places_have_a_kind(client, northbridge):
    got = rows(client, northbridge, "MATCH (p:Place) RETURN p.ref, p.kind ORDER BY p.ref")
    assert got == [
        ["northbridge:chat:finance", "chat"],
        ["northbridge:erp:log", "tracker"],
        ["northbridge:inbox:ap", "list"],
        ["northbridge:portal:vendors", "portal"],
    ]


def test_the_controller_stops_being_a_visible_approver_only_in_the_authority_edges(
    client, northbridge
):
    # Leave does not remove Marcus from the chat channel: he still participates there.
    marcus = parse.hid(synthetic.CONTROLLER, parse.default_salt())
    got = rows(
        client,
        northbridge,
        "MATCH (:Actor {hid: $h})-[:PARTICIPATES_IN]->(p:Place {ref: 'northbridge:chat:finance'}) "
        "RETURN count(p)",
        {"h": marcus},
    )
    assert got == [[1]]


def test_mail_population_is_idempotent_and_folds_since_and_last(client):
    g = f"org_vis{uuid.uuid4().hex[:8]}"
    index = {
        "messages": [
            {"msg": 2, "status": 200, "author_hash": "h1", "date_utc": "2011-03-17T13:11:08Z"},
            {"msg": 4, "status": 200, "author_hash": "h1", "date_utc": "2011-03-17T17:46:04Z"},
            {"msg": 5, "status": 404, "author_hash": None, "date_utc": None},
        ]
    }
    try:
        mail = pv.mail_events(index)
        assert [m["ref"] for m in mail] == ["xz-devel:msg00002", "xz-devel:msg00004"]
        first = pv.populate(client, g, mail)
        second = pv.populate(client, g, mail)
        assert first == second
        assert first["participates_in"] == 1 and first["recorded_in"] == 2
        e = rows(client, g, "MATCH ()-[e:PARTICIPATES_IN]->() RETURN e.since, e.last_at")
        assert e == [[pv.epoch("2011-03-17T13:11:08Z"), pv.epoch("2011-03-17T17:46:04Z")]]
    finally:
        client.drop(g)
