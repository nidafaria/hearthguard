"""Who-saw-what (spec §9) and already_acknowledged(). Real FalkorDB.

Hand-worked expectations (times are plain integers, T = 1000):
  - PARTICIPATES_IN rows: (a, list, since 100, last 300), then (a, list, since 50, last 200).
    Merged result: since = min(100, 50) = 50, last_at = max(300, 200) = 300. One edge.
  - A finding with an OwnerDecision at 500 is acknowledged at now = 1000; one decided at 1500 is
    not yet (it is after now); a finding with no decision is not acknowledged.
  - Writing the same rows twice changes no count.
"""

import pytest

from core.memory import who_saw as ws
from tests.fixtures.bd import q


def _counts(client, org):
    nodes = q(client, org, "MATCH (n) RETURN count(n)").result_set[0][0]
    edges = q(client, org, "MATCH ()-[r]->() RETURN count(r)").result_set[0][0]
    return nodes, edges


def test_participates_in_keeps_earliest_since_and_latest_last(client, org_graph):
    g = f"org_{org_graph}"
    ws.write_participation(client, g, [{"hid": "a", "place": "list", "since": 100, "last_at": 300}])
    ws.write_participation(client, g, [{"hid": "a", "place": "list", "since": 50, "last_at": 200}])
    r = q(
        client,
        org_graph,
        "MATCH (:Actor {hid:'a'})-[e:PARTICIPATES_IN]->(:Place {ref:'list'}) "
        "RETURN e.since, e.last_at",
    ).result_set
    assert r == [[50, 300]]


def test_watches_keeps_earliest_since(client, org_graph):
    g = f"org_{org_graph}"
    ws.write_watches(client, g, [{"role": "maintainer", "place": "list", "since": 120}])
    ws.write_watches(client, g, [{"role": "maintainer", "place": "list", "since": 90}])
    r = q(client, org_graph, "MATCH (:Role)-[w:WATCHES]->(:Place) RETURN w.since").result_set
    assert r == [[90]]


def test_a_second_identical_write_changes_no_count(client, org_graph):
    g = f"org_{org_graph}"
    rows = [{"hid": "a", "place": "list", "since": 100, "last_at": 300}]
    ws.write_participation(client, g, rows)
    before = _counts(client, org_graph)
    ws.write_participation(client, g, rows)
    assert _counts(client, org_graph) == before


@pytest.fixture
def decided(client, org_graph):
    g = f"org_{org_graph}"
    q(
        client,
        org_graph,
        "CREATE (:Finding {id: 'f-ack'}), (:Finding {id: 'f-later'}), (:Finding {id: 'f-none'})",
    )
    q(
        client,
        org_graph,
        "MATCH (f:Finding {id:'f-ack'}) "
        "CREATE (:OwnerDecision {text: 'known', at: 500})-[:ABOUT]->(f)",
    )
    q(
        client,
        org_graph,
        "MATCH (f:Finding {id:'f-later'}) "
        "CREATE (:OwnerDecision {text: 'later', at: 1500})-[:ABOUT]->(f)",
    )
    return g


def test_an_owner_decision_before_now_acknowledges_the_finding(client, decided):
    assert ws.already_acknowledged(client, decided, "f-ack", now=1000) is True


def test_a_decision_after_now_does_not_yet_acknowledge(client, decided):
    assert ws.already_acknowledged(client, decided, "f-later", now=1000) is False


def test_a_finding_with_no_decision_is_not_acknowledged(client, decided):
    assert ws.already_acknowledged(client, decided, "f-none", now=1000) is False


def test_the_liaison_would_not_resend_an_acknowledged_finding(client, decided):
    """Try to break the rule: a second call for the acknowledged finding still says yes."""
    for _ in range(2):
        assert ws.already_acknowledged(client, decided, "f-ack", now=2000) is True
