"""The `why` query (spec 7.6) returns each supporting claim with its quote and source link.

The real xz claims all fall before the first decision quarter, so no real Finding has a claim in its
window yet. This test builds a small graph with one Finding, one Claim, one Span and one mail
Source on a real FalkorDB, then runs the live query through the read-only guard.
"""

from core.agents import inbox_graph as ig
from core.agents import why as why_mod
from core.agents.cases import Case
from core.graph.client import FalkorClient

ORG = "whytest"
GRAPH = f"org_{ORG}"
CASE = Case(
    id="whytest",
    org=ORG,
    label="SYNTHETIC test graph",
    synthetic=True,
    decision_file="decision_status.json",
    detail_files=(),
    hardening_file=None,
)
QUARTER = "2021-Q1"
MSG = "msg00402"


def _build(client: FalkorClient) -> None:
    client.drop(GRAPH)
    ig.ensure_schema(client, GRAPH)
    fid = ig.finding_id(CASE, QUARTER)
    client.query(
        GRAPH,
        """CREATE (f:Finding {id: $fid, moves: ['PRESSURE'], status: 'held', at: 1})
           CREATE (a:Actor {hid: 'hashed-actor-1', kind: 'human'})
           CREATE (c:Claim {id: $cid, kind: 'CAPACITY_STATEMENT', at: 1610134610})
           CREATE (sp:Span {id: $cid + ':span', text: 'it will be a while', offset: 808})
           CREATE (src:Source {type: 'mail', ref: $msg})
           WITH f, a, c, sp, src
           CREATE (f)-[:SUPPORTED_BY]->(c), (c)-[:FROM]->(sp), (src)-[:HAS]->(sp),
                  (a)-[:ASSERTED]->(c)""",
        {"fid": fid, "cid": "msg00402:CAPACITY_STATEMENT:808", "msg": MSG},
        timeout_ms=20_000,
    )


def test_why_returns_the_quote_and_the_source_link():
    client = FalkorClient()
    _build(client)
    out = why_mod.run_why(client, CASE, QUARTER)
    assert out["query"]["rows"] == 1
    row = out["rows"][0]
    assert row["kind"] == "Claim"
    assert row["quote"] == "it will be a while"
    assert row["link"] == why_mod.source_link("mail", MSG, None)
    assert row["link"].startswith("http") and row["link"].endswith("msg00402.html")


def test_why_query_is_the_guarded_read_with_a_timeout():
    client = FalkorClient()
    _build(client)
    out = why_mod.run_why(client, CASE, QUARTER)
    assert out["query"]["timeout_ms"] > 0
    assert out["query"]["guard"].startswith("GRAPH.RO_QUERY")
    assert "LIMIT 200" in out["query"]["cypher"]
