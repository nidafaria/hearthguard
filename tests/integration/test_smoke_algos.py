"""Smoke-test the FalkorDB procedures the product depends on, on the pinned image.

Source: docs/HEARTHGUARD.md §5.1 (procedure facts), §7.4 (takeover cost and guardians).
Real FalkorDB only (CLAUDE.md). Every graph here is tiny and hand-built, and the expected
values are derived by hand in the comments. Run with: make smoke-algos
"""

import time

import pytest
from redis.exceptions import ResponseError

from core.graph.client import FalkorClient


def record(proc: str, signature: str, yields: list[str]) -> None:
    """Print the observed signature and yield fields (visible with pytest -s)."""
    print(f"\n[smoke] {proc}\n        signature: {signature}\n        yields:    {yields}")


def yield_names(result) -> list[str]:
    # result.header is [[type, name], ...]; we only need the names.
    return [col[1] for col in result.header]


def build(client: FalkorClient, name: str, node_names: list[str], edges) -> None:
    """Create :N nodes {n: ...} and directed :E edges (u, v, w) in graph `name`."""
    client.query(name, "UNWIND $names AS n CREATE (:N {n: n})", {"names": node_names})
    for u, v, w in edges:
        client.query(
            name,
            "MATCH (a:N {n: $u}), (b:N {n: $v}) CREATE (a)-[:E {w: $w}]->(b)",
            {"u": u, "v": v, "w": w},
        )


@pytest.fixture(scope="module")
def client() -> FalkorClient:
    return FalkorClient()


@pytest.fixture
def g(client, request):
    name = "smoke_" + request.node.name.removeprefix("test_")
    client.drop(name)
    yield name
    client.drop(name)


def test_sppaths_yields_path_and_weight(client, g):
    # Edges a->b (w=1), b->c (w=2), a->c (w=5). Shortest weighted a->c is 1+2 = 3, not 5.
    build(client, g, ["a", "b", "c"], [("a", "b", 1), ("b", "c", 2), ("a", "c", 5)])
    r = client.query(
        g,
        """MATCH (a:N {n:'a'}), (c:N {n:'c'})
           CALL algo.SPpaths({sourceNode: a, targetNode: c, relTypes: ['E'], weightProp: 'w'})
           YIELD path, pathWeight
           RETURN path, pathWeight""",
    )
    fields = yield_names(r)
    record("algo.SPpaths", "algo.SPpaths({sourceNode, targetNode, relTypes, weightProp})", fields)
    assert fields == ["path", "pathWeight"]
    assert r.result_set[0][1] == 3


def test_maxflow_rejects_two_relationship_types(client, g):
    build(client, g, ["a"], [])
    with pytest.raises(ResponseError) as exc:
        client.query(
            g,
            """MATCH (s:N {n:'a'})
               CALL algo.maxFlow({sourceNodes:[s], targetNodes:[s],
                 capacityProperty:'c', relationshipTypes:['CAP','E']})
               YIELD maxFlow RETURN maxFlow""",
        )
    msg = str(exc.value)
    print(f"\n[smoke] algo.maxFlow (two types) error: {msg}")
    assert "exactly one type" in msg


# Projection and guardians query from docs/HEARTHGUARD.md §7.4, copied as-is.
GUARDIAN_PROJECTION = """
MATCH (k:Actor)-[:CAN_GRANT]->(p:Privilege {kind:$privilege})
MERGE (ki:Flow {id: k.hid + ':in'})  MERGE (ko:Flow {id: k.hid + ':out'})
MERGE (ki)-[:CAP {c: 1}]->(ko)
MERGE (src:Flow {id:'OUTSIDER'})     MERGE (dst:Flow {id:'PRIV:' + $privilege})
MERGE (src)-[:CAP {c: 1000000}]->(ki)
MERGE (ko)-[:CAP {c: 1000000}]->(dst)
"""

GUARDIANS = """
MATCH (s:Flow {id:'OUTSIDER'}), (t:Flow {id:'PRIV:' + $privilege})
CALL algo.maxFlow({sourceNodes:[s], targetNodes:[t],
  capacityProperty:'c', relationshipTypes:['CAP']})
YIELD maxFlow
RETURN maxFlow AS guardians
"""


def guardians_for(client: FalkorClient, name: str, keepers: list[str]) -> tuple[int, list[str]]:
    client.query(
        name,
        "CREATE (:Privilege {kind:'deploy'})",
    )
    for hid in keepers:
        client.query(
            name,
            """MATCH (p:Privilege {kind:'deploy'})
               CREATE (:Actor {hid: $hid})-[:CAN_GRANT]->(p)""",
            {"hid": hid},
        )
    client.query(name, GUARDIAN_PROJECTION, {"privilege": "deploy"})
    r = client.query(name, GUARDIANS, {"privilege": "deploy"})
    return r.result_set[0][0], yield_names(r)


def test_guardians_one_middle_person_is_1(client, g):
    # OUTSIDER -> k1 -> PRIV. Every route passes through k1, so one person is the cut.
    value, fields = guardians_for(client, g, ["k1"])
    record(
        "algo.maxFlow (guardians projection)",
        "algo.maxFlow({sourceNodes, targetNodes, capacityProperty, relationshipTypes})",
        fields,
    )
    assert value == 1


def test_guardians_two_parallel_people_is_2(client, g):
    # OUTSIDER -> k1 -> PRIV and OUTSIDER -> k2 -> PRIV. Two disjoint routes, so cut = 2.
    value, fields = guardians_for(client, g, ["k1", "k2"])
    print(f"\n[smoke] guardians (two parallel people) yields: {fields}")
    assert value == 2


def test_wcc_components_on_two_clusters(client, g):
    # Cluster A: a1-a2. Cluster B: b1-b2. Two components.
    build(
        client,
        g,
        ["a1", "a2", "b1", "b2"],
        [("a1", "a2", 1), ("a2", "a1", 1), ("b1", "b2", 1), ("b2", "b1", 1)],
    )
    r = client.query(
        g,
        """CALL algo.WCC({nodeLabels:['N'], relationshipTypes:['E']})
           YIELD node, componentId RETURN node.n AS n, componentId""",
    )
    fields = yield_names(r)
    record("algo.WCC", "algo.WCC({nodeLabels, relationshipTypes})", fields)
    comp = {row[0]: row[1] for row in r.result_set}
    assert fields == ["n", "componentId"]
    assert comp["a1"] == comp["a2"]
    assert comp["b1"] == comp["b2"]
    assert comp["a1"] != comp["b1"]


def test_label_propagation_separates_two_cliques(client, g):
    # Two disconnected triangles. Labels cannot cross a component boundary.
    nodes = ["a1", "a2", "a3", "b1", "b2", "b3"]
    edges = []
    for group in (["a1", "a2", "a3"], ["b1", "b2", "b3"]):
        for u in group:
            for v in group:
                if u != v:
                    edges.append((u, v, 1))
    build(client, g, nodes, edges)
    r = client.query(
        g,
        """CALL algo.labelPropagation({nodeLabels:['N'], relationshipTypes:['E']})
           YIELD node, communityId RETURN node.n AS n, communityId""",
    )
    fields = yield_names(r)
    record(
        "algo.labelPropagation", "algo.labelPropagation({nodeLabels, relationshipTypes})", fields
    )
    labels = {row[0]: row[1] for row in r.result_set}
    assert fields == ["n", "communityId"]
    assert set(labels) == set(nodes)
    a_labels = {labels[n] for n in ["a1", "a2", "a3"]}
    b_labels = {labels[n] for n in ["b1", "b2", "b3"]}
    print(f"\n[smoke] labelPropagation labels: A={sorted(a_labels)} B={sorted(b_labels)}")
    assert a_labels.isdisjoint(b_labels)
    assert len(a_labels) == 1 and len(b_labels) == 1


def test_betweenness_star_hub(client, g):
    # Hub h with leaves l1..l4, edges in both directions. Each ordered leaf pair (li, lj)
    # has its only shortest path through h: 4 * 3 = 12 ordered pairs, so hub = 12.
    # Leaves lie on no shortest path between other nodes, so each leaf = 0.
    leaves = ["l1", "l2", "l3", "l4"]
    edges = []
    for leaf in leaves:
        edges.append(("h", leaf, 1))
        edges.append((leaf, "h", 1))
    build(client, g, ["h"] + leaves, edges)
    r = client.query(
        g,
        """CALL algo.betweenness({nodeLabels:['N'], relationshipTypes:['E']})
           YIELD node, score RETURN node.n AS n, score""",
    )
    fields = yield_names(r)
    record("algo.betweenness", "algo.betweenness({nodeLabels, relationshipTypes})", fields)
    score = {row[0]: row[1] for row in r.result_set}
    assert fields == ["n", "score"]
    assert score["h"] == 12
    assert all(score[leaf] == 0 for leaf in leaves)


def test_graph_copy_is_independent(client, g):
    build(client, g, ["a", "b", "c"], [("a", "b", 1), ("b", "c", 1)])
    dst = g + "_copy"
    client.drop(dst)
    try:
        client.copy(g, dst)
        client.query(dst, "CREATE (:N {n: 'extra'})")
        src_count = client.query(g, "MATCH (n) RETURN count(n)").result_set[0][0]
        dst_count = client.query(dst, "MATCH (n) RETURN count(n)").result_set[0][0]
        print(
            f"\n[smoke] GRAPH.COPY: src={src_count} nodes, dst={dst_count} nodes after write to dst"
        )
        assert src_count == 3
        assert dst_count == 4
    finally:
        client.drop(dst)


def test_cch_is_unavailable(client, g):
    build(client, g, ["a"], [])
    with pytest.raises(ResponseError) as exc:
        client.query(g, "CALL algo.CCH({}) YIELD x RETURN x")
    msg = str(exc.value)
    print(f"\n[smoke] algo.CCH error: {msg}")
    assert "Unknown function" in msg
    assert "algo.CCH" in msg


def test_query_timeout_is_enforced(client, g):
    # A 900M-row cartesian product cannot finish in 50 ms, so the server must cut it off.
    start = time.monotonic()
    with pytest.raises(ResponseError) as exc:
        client.query(
            g,
            "UNWIND range(1,30000) AS a UNWIND range(1,30000) AS b RETURN count(*)",
            timeout_ms=50,
        )
    elapsed_ms = (time.monotonic() - start) * 1000
    print(f"\n[smoke] per-query timeout 50 ms -> {exc.value} after {elapsed_ms:.0f} ms")
    assert "timed out" in str(exc.value)
    assert elapsed_ms < 2000
