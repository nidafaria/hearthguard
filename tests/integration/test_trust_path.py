"""Trust path (spec §7.6): algo.SPpaths from a young actor to a sensitive privilege. Real FalkorDB.

Hand-worked graph (T = 1000; hashed ids are letters):
    y1 --VOUCHED_FOR--> cand --GRANTED--> release        y1's path: 2 hops, weight 2
    y2 --REVIEWED--> keeper --GRANTED--> release         y2's path: 2 hops, weight 2
    y3 --VOUCHED_FOR--> y1 --VOUCHED_FOR--> cand ...     y3's shortest: 3 hops, weight 3
    lonely                                               no edges, so NO PATH
    a VOUCH claim dated T+1 (y4 -> cand) is in the future, so y4 has NO PATH at T.
"""

import pytest

from core.graph.as_of import MissingAsOfError
from core.takeover import trust_path as tp
from tests.fixtures.bd import q

T = 1_000


def build(client, org):
    q(client, org, "CREATE (:Privilege {kind: 'release', sensitive: true})")
    for h in ("y1", "y2", "y3", "y4", "cand", "keeper", "lonely"):
        q(client, org, "MERGE (:Actor {hid: $h})", {"h": h})
    for h in ("cand", "keeper"):
        q(
            client,
            org,
            "MATCH (a:Actor {hid: $h}), (p:Privilege) CREATE (a)-[:GRANTED {at: 500}]->(p)",
            {"h": h},
        )
    for voucher, cand, at in (("y1", "cand", 100), ("y3", "y1", 200), ("y4", "cand", T + 1)):
        q(
            client,
            org,
            "MATCH (v:Actor {hid: $v}) CREATE (v)-[:ASSERTED]->"
            "(:Claim {id: $id, kind: 'VOUCH', target_hid: $c, at: $at})",
            {"v": voucher, "c": cand, "at": at, "id": f"{voucher}-{cand}"},
        )
    q(
        client,
        org,
        "MATCH (r:Actor {hid:'y2'}), (k:Actor {hid:'keeper'}) CREATE (r)-[:REVIEWED {at: 50}]->(k)",
    )


@pytest.mark.parametrize(
    ("actor", "status", "weight", "path"),
    [
        ("y1", tp.COMPUTED, 2, ["y1", "cand", "PRIV:release"]),
        ("y2", tp.COMPUTED, 2, ["y2", "keeper", "PRIV:release"]),
        ("y3", tp.COMPUTED, 3, ["y3", "y1", "cand", "PRIV:release"]),
        ("lonely", tp.NO_PATH, None, []),
        ("y4", tp.NO_PATH, None, []),  # its only vouch is dated after T
    ],
)
def test_hand_worked_paths(client, org_graph, actor, status, weight, path):
    build(client, org_graph)
    r = tp.trust_path(client, org_graph, actor, "release", T)
    assert (r.status, r.weight, r.path) == (status, weight, path)
    assert any("SPpaths" in x["query"] for x in r.queries)
    assert r.query_ms is not None


def test_hops_name_the_relationship_types(client, org_graph):
    build(client, org_graph)
    r = tp.trust_path(client, org_graph, "y2", "release", T)
    assert r.hops == ["REVIEWED", "GRANTED"]


def test_no_privilege_data_is_not_computed(client, org_graph):
    r = tp.trust_path(client, org_graph, "y1", "release", T)
    assert r.status == tp.NOT_COMPUTED
    assert "no CAN_GRANT or Privilege data" in r.reason


def test_a_missing_graph_is_not_computed(client):
    r = tp.trust_path(client, "bd_does_not_exist", "y1", "release", T)
    assert r.status == tp.NOT_COMPUTED and "does not exist" in r.reason


def test_missing_T_is_refused(client, org_graph):
    with pytest.raises(MissingAsOfError):
        tp.trust_path(client, org_graph, "y1", "release", None)


def test_the_org_graph_is_only_read_and_scratch_is_dropped(client, org_graph):
    build(client, org_graph)
    before = q(client, org_graph, "MATCH (n) RETURN count(n)").result_set[0][0]
    tp.trust_path(client, org_graph, "y1", "release", T)
    assert q(client, org_graph, "MATCH (n) RETURN count(n)").result_set[0][0] == before
    names = {
        g if isinstance(g, str) else g.decode() for g in client.db.execute_command("GRAPH.LIST")
    }
    assert not [n for n in names if n.startswith("takeover_") and org_graph in n]
