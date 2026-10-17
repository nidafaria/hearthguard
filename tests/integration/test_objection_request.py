"""Objection and Request writers (spec 6.1) on a real FalkorDB, scratch org only.

add_objection hangs an Objection on a Finding; add_request hangs a Request on the Objection. Both
are MERGE on a key built from their content, so a second call changes nothing. An objection on a
Finding that does not exist writes nothing. No Skeptic calls these yet (eval/results/blockers_a.md).
"""

import pytest

from core.agents import inbox_graph as ig
from core.graph.client import FalkorClient
from core.graph.schema import apply_schema
from tests.integration.scratch_graphs import drop_owned, new_org_id

FID = "finding:test:2021-Q4"


@pytest.fixture
def org():
    client = FalkorClient()
    oid = new_org_id()
    graph = f"org_{oid}"
    client.drop(graph)
    apply_schema(client, graph)
    client.query(graph, "MERGE (f:Finding {id: $id})", {"id": FID}, timeout_ms=10_000)
    yield client, graph
    drop_owned(client, oid)


def _count(c, g, cypher, params=None):
    return c.query(g, cypher, params or {}, timeout_ms=10_000).result_set[0][0]


def test_an_objection_is_stored_on_its_finding(org):
    c, g = org
    oid = ig.add_objection(c, g, FID, "the release looks like the usual one", 100)
    row = c.query(
        g,
        "MATCH (o:Objection {id: $oid})-[:ON]->(f:Finding) "
        "RETURN f.id, o.by, o.reason, o.open, o.at",
        {"oid": oid},
        timeout_ms=10_000,
    ).result_set
    assert row == [[FID, "skeptic", "the release looks like the usual one", True, 100]]


def test_a_second_identical_objection_adds_nothing(org):
    c, g = org
    a = ig.add_objection(c, g, FID, "same reason", 100)
    b = ig.add_objection(c, g, FID, "same reason", 200)
    assert a == b
    assert _count(c, g, "MATCH (o:Objection) RETURN count(o)") == 1
    assert _count(c, g, "MATCH (:Objection)-[e:ON]->() RETURN count(e)") == 1


def test_an_objection_on_a_missing_finding_writes_nothing(org):
    c, g = org
    ig.add_objection(c, g, "finding:missing", "reason", 100)
    assert _count(c, g, "MATCH (o:Objection) RETURN count(o)") == 0


def test_a_request_hangs_on_its_objection_and_starts_open(org):
    c, g = org
    oid = ig.add_objection(c, g, FID, "reason", 100)
    rid = ig.add_request(c, g, oid, "who else approved this release?", "skeptic", "investigator")
    row = c.query(
        g,
        "MATCH (r:Request {id: $rid})-[:FOR]->(o:Objection) "
        "RETURN o.id, r.from, r.to, r.question, r.status",
        {"rid": rid},
        timeout_ms=10_000,
    ).result_set
    assert row == [[oid, "skeptic", "investigator", "who else approved this release?", "open"]]


def test_a_second_identical_request_adds_nothing_and_keeps_its_status(org):
    c, g = org
    oid = ig.add_objection(c, g, FID, "reason", 100)
    rid = ig.add_request(c, g, oid, "question?", "skeptic", "investigator")
    c.query(
        g, "MATCH (r:Request {id: $r}) SET r.status = 'answered'", {"r": rid}, timeout_ms=10_000
    )
    assert ig.add_request(c, g, oid, "question?", "skeptic", "investigator") == rid
    assert _count(c, g, "MATCH (r:Request) RETURN count(r)") == 1
    assert _count(c, g, "MATCH (r:Request) RETURN r.status") == "answered"


def test_a_request_on_a_missing_objection_writes_nothing(org):
    c, g = org
    ig.add_request(c, g, "objection:missing", "question?", "skeptic", "investigator")
    assert _count(c, g, "MATCH (r:Request) RETURN count(r)") == 0
