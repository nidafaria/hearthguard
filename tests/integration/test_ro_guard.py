"""Read-only guard on the real container. Writes are refused before they reach the server."""

import pytest
from redis.exceptions import ResponseError

from core.graph.client import FalkorClient
from core.graph.ro_guard import ReadOnlyViolation, ro_query


@pytest.fixture(scope="module")
def client() -> FalkorClient:
    return FalkorClient()


@pytest.fixture(scope="module")
def dead_client() -> FalkorClient:
    # Nothing listens on port 1. A rejection here proves the guard ran before any network call.
    return FalkorClient(host="localhost", port=1)


@pytest.fixture
def g(client, request):
    name = "ro_" + request.node.name.removeprefix("test_")
    client.drop(name)
    client.query(name, "CREATE (:Action {ref: 'r1'}), (:Action {ref: 'r2'})")
    yield name
    client.drop(name)


def test_read_passes_through_ro_query(client, g):
    r = ro_query(client, g, "MATCH (n:Action) RETURN n.ref AS ref ORDER BY ref LIMIT 10")
    assert [row[0] for row in r.result_set] == ["r1", "r2"]


WRITES = [
    "CREATE (:X {id: 1}) RETURN 1 LIMIT 1",
    "MATCH (n:Action) SET n.ref = 'hacked' RETURN n LIMIT 1",
    "MATCH (n:Action) DELETE n LIMIT 1",
    "MERGE (:Action {ref: 'r3'}) RETURN 1 LIMIT 1",
    "CREATE FULLTEXT INDEX FOR (n:Action) ON (n.ref)",
]


@pytest.mark.parametrize("cypher", WRITES)
def test_write_is_rejected_before_server(dead_client, cypher):
    # If the guard did not run first, the dead client would raise a connection error instead.
    with pytest.raises(ReadOnlyViolation):
        ro_query(dead_client, "org_x", cypher)


def test_server_also_refuses_write_on_ro_path(client, g):
    # Defence in depth: even bypassing our guard, GRAPH.RO_QUERY refuses a write.
    with pytest.raises(ResponseError, match="read-only"):
        client.graph(g).ro_query("CREATE (:Action {ref: 'nope'})", timeout=2000)
    count = client.query(g, "MATCH (n:Action) RETURN count(n)").result_set[0][0]
    assert count == 2
