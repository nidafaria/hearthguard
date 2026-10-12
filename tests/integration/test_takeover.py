"""Takeover cost and guardians on hand-built graphs and on real org_xz. Real FalkorDB, no mocks.

Rule under test is PROPOSED and every result is provisional (docs/decisions/0001-outsider-edges.md).
"""

import json
from pathlib import Path

import pytest
from redis.exceptions import ResponseError

from core.graph.as_of import MissingAsOfError
from core.graph.client import FalkorClient
from core.takeover import cost
from core.takeover import guardians as gmod
from core.takeover import scratch as sc
from eval import xz_takeover_status
from packs.oss import xz_graph
from tests.fixtures.takeover_cases import CASE_E_AFTER, CASES, PRIV, Case, T

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def client() -> FalkorClient:
    return FalkorClient()


def graph_names(client: FalkorClient) -> set[str]:
    return {
        g if isinstance(g, str) else g.decode() for g in client.db.execute_command("GRAPH.LIST")
    }


def scratch_names(client: FalkorClient) -> list[str]:
    return sorted(n for n in graph_names(client) if n.startswith("takeover_"))


@pytest.fixture
def org(client, request):
    org = "tk_" + request.node.name.split("[")[0].removeprefix("test_")[:30]
    client.drop(sc.graph_for(org))
    yield org
    client.drop(sc.graph_for(org))


def run_case(client: FalkorClient, org: str, case: Case):
    client.drop(sc.graph_for(org))
    case.build(client, sc.graph_for(org))
    return cost.takeover_cost(client, org, PRIV, case.T), gmod.guardians(client, org, PRIV, case.T)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_fixture_has_the_hand_derived_values(client, org, case):
    c, g = run_case(client, org, case)
    print(f"\n[{case.name}] cost={c.cost} ({c.status}, {c.reason}) guardians={g.guardians}")
    assert c.cost == case.cost
    assert c.reason == case.cost_reason
    assert g.guardians == case.guardians
    assert g.status == gmod.COMPUTED
    if case.path:
        assert tuple(c.path) == case.path
    assert c.status == (cost.COMPUTED if case.cost is not None else cost.NO_PATH)
    # Every output is provisional and carries the queries that produced it.
    assert c.provisional and g.provisional and "PROPOSED" in c.rule
    assert c.query_ms is not None and g.query_ms is not None
    assert any("SPpaths" in q["query"] for q in c.queries)
    assert any("maxFlow" in q["query"] for q in g.queries)
    assert scratch_names(client) == []


def test_grant_dated_after_T_is_excluded_then_included(client, org):
    before, g_before = run_case(client, org, CASES[4])  # case e at T
    assert (before.cost, before.reason, g_before.guardians) == (None, "no path", 0)
    after, g_after = run_case(client, org, CASE_E_AFTER)  # same graph at T + 1
    assert (after.cost, g_after.guardians) == (1, 1)


def test_no_path_is_a_result_not_an_error(client, org):
    c, g = run_case(client, org, CASES[3])
    assert c.status == cost.NO_PATH and c.cost is None and c.reason == "no path"
    assert g.guardians == 0 and g.reason == "no route from OUTSIDER"


def test_more_grants_than_one_page_are_all_read(client, org):
    # 1,200 keepers, each able to grant alone (approvals_required 1). The read is capped at
    # 1,000 rows a page, so a result that is not paged would stop at 1,000.
    # Cost: any one keeper suffices, so 1. Guardians: 1,200 disjoint routes need 1,200 people.
    g = sc.graph_for(org)
    client.query(g, "CREATE (:Privilege {kind: $k, sensitive: true})", {"k": PRIV})
    client.query(
        g,
        "UNWIND range(1, 1200) AS i CREATE (:Actor {hid: 'k' + toString(i)})",
        timeout_ms=30_000,
    )
    client.query(
        g,
        "MATCH (a:Actor), (p:Privilege {kind: $k}) "
        "CREATE (a)-[e:CAN_GRANT]->(p) SET e.approvals_required = 1, e.at = 1",
        {"k": PRIV},
        timeout_ms=30_000,
    )
    c = cost.takeover_cost(client, org, PRIV, T, timeout_ms=30_000)
    n = gmod.guardians(client, org, PRIV, T, timeout_ms=30_000)
    pages = [q for q in n.queries if q["name"] == "read_grants"]
    print(f"\n[paging] cost={c.cost} guardians={n.guardians} read pages={len(pages)}")
    assert c.cost == 1
    assert n.guardians == 1200
    assert len(pages) == 2


def norm(cypher: str) -> str:
    lines = [ln for ln in cypher.splitlines() if not ln.strip().startswith("//")]
    return " ".join(" ".join(lines).split()).rstrip(";").strip()


def test_projection_and_guardians_query_are_the_spec_text():
    spec = (REPO / "docs" / "HEARTHGUARD.md").read_text(encoding="utf-8")
    start = spec.index("```cypher\n// Projection")
    end = spec.index("```", start + 10)
    projection, guardians_q = spec[start + len("```cypher\n") : end].split("// Guardians")
    assert norm(projection) == norm(gmod.PROJECTION)
    assert norm(guardians_q) == norm(gmod.GUARDIANS_QUERY)


def test_maxflow_rejects_two_relationship_types(client):
    with sc.scratch_graph(client, "tk_two_types") as scratch:
        client.query(scratch, "CREATE (:Flow {id: 'OUTSIDER'})-[:CAP {c: 1}]->(:Flow {id: 'T'})")
        with pytest.raises(ResponseError) as exc:
            client.query(
                scratch,
                "MATCH (s:Flow {id: 'OUTSIDER'}), (t:Flow {id: 'T'}) "
                "CALL algo.maxFlow({sourceNodes: [s], targetNodes: [t], capacityProperty: 'c', "
                "relationshipTypes: ['CAP', 'CAN_GRANT']}) YIELD maxFlow RETURN maxFlow",
            )
    print(f"\n[maxFlow two types] error message: {exc.value}")
    assert "exactly one type" in str(exc.value)


def test_scratch_graph_is_deleted_after_a_failed_query(client, org, monkeypatch):
    CASES[0].build(client, sc.graph_for(org))
    seen = {}
    real_fill = sc.fill_scratch

    def watch(cl, scratch, *args, **kwargs):
        real_fill(cl, scratch, *args, **kwargs)
        seen[scratch] = scratch in graph_names(cl)  # the scratch graph really existed

    monkeypatch.setattr(sc, "fill_scratch", watch)
    monkeypatch.setattr(gmod, "GUARDIANS_QUERY", "MATCH (s:Flow RETURN s")  # invalid Cypher
    with pytest.raises(ResponseError):
        gmod.guardians(client, org, PRIV, T, run="tk_fail_g")
    assert seen == {"takeover_tk_fail_g": True}
    assert "takeover_tk_fail_g" not in graph_names(client)

    seen.clear()
    monkeypatch.setattr(cost, "PATH_QUERY", "MATCH (s:Flow RETURN s")
    with pytest.raises(ResponseError):
        cost.takeover_cost(client, org, PRIV, T, run="tk_fail_c")
    assert seen == {"takeover_tk_fail_c": True}
    assert scratch_names(client) == []


def test_org_graph_is_only_read(client, org):
    run_case(client, org, CASES[1])
    g = sc.graph_for(org)
    nodes = client.query(g, "MATCH (n) RETURN labels(n)[0] AS l, count(n) ORDER BY l").result_set
    edges = client.query(g, "MATCH ()-[r]->() RETURN type(r) AS t, count(r) ORDER BY t").result_set
    assert nodes == [["Actor", 2], ["Privilege", 1]]  # no Flow, no OUTSIDER
    assert edges == [["CAN_GRANT", 2]]  # no OUTSIDER_ENTRY, no CAP


def test_no_actor_holds_a_cost_or_guardians_value(client, org):
    run_case(client, org, CASES[0])
    rows = client.query(sc.graph_for(org), "MATCH (a:Actor) RETURN a").result_set
    assert rows
    for (actor,) in rows:
        assert not {k for k in actor.properties if "cost" in k or "guardian" in k}


def test_missing_T_is_refused_before_any_query(client):
    with pytest.raises(MissingAsOfError):
        cost.takeover_cost(client, "anything", PRIV, None)
    with pytest.raises(MissingAsOfError):
        gmod.guardians(client, "anything", PRIV, None)


def test_missing_org_graph_is_not_computed_with_its_own_reason(client):
    client.drop("org_tk_nope")
    c = cost.takeover_cost(client, "tk_nope", PRIV, T)
    g = gmod.guardians(client, "tk_nope", PRIV, T)
    assert (c.status, g.status) == (cost.NOT_COMPUTED, gmod.NOT_COMPUTED)
    assert "does not exist" in c.reason and "does not exist" in g.reason
    assert "org_tk_nope" not in graph_names(client)  # a read did not create it


def test_real_xz_is_not_computed_and_writes_no_finding(client, xz_org):
    status = xz_takeover_status.build_status(client)
    print(f"\n[xz] {json.dumps({k: status[k]['status'] for k in ('takeover_cost', 'guardians')})}")
    for part in ("takeover_cost", "guardians"):
        assert status[part]["status"] == "NOT COMPUTED"
        assert status[part]["value"] is None
        assert "no CAN_GRANT or Privilege data in org_xz" in status[part]["reason"]
        assert "git history has no grant record" in status[part]["reason"]
        assert status[part]["queries"] and "Privilege" in status[part]["queries"][0]["query"]
    assert status["provisional"] is True
    nodes = xz_graph.graph_counts(client, "org_xz")["nodes"]
    assert "Privilege" not in nodes and "Flow" not in nodes
    for (actor,) in client.query("org_xz", "MATCH (a:Actor) RETURN a").result_set:
        assert not {k for k in actor.properties if "cost" in k or "guardian" in k}
    assert scratch_names(client) == []


def test_committed_status_file_matches_when_present(xz_org):
    out = xz_takeover_status.OUT
    if not out.exists():
        pytest.skip("status file not written yet (run make takeover-xz)")
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["takeover_cost"]["status"] == saved["guardians"]["status"] == "NOT COMPUTED"
    assert saved["takeover_cost"]["value"] is None and saved["guardians"]["value"] is None
