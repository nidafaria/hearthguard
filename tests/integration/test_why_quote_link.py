"""The `why` query (spec 7.6) returns each supporting claim with its quote and source link.

The real xz claims all fall before the first decision quarter, so no real Finding has a claim in its
window yet. This test builds a small graph with one Finding, one Claim, one Span and one mail
Source in a scratch org (tests/integration/scratch_graphs.py), then runs the live query through
the read-only guard. Teardown drops only that scratch graph.
"""

import dataclasses

import pytest

from core.agents import inbox_graph as ig
from core.agents import why as why_mod
from core.agents.cases import CASES
from core.graph.client import FalkorClient
from tests.integration.scratch_graphs import drop_owned, new_org_id

pytestmark = pytest.mark.usefixtures("real_graphs_untouched")

QUARTER = "2021-Q1"
MSG = "msg00402"


@pytest.fixture
def case():
    org = new_org_id()
    try:
        yield dataclasses.replace(CASES["xz"], org=org)
    finally:
        drop_owned(FalkorClient(), org)


def _build(client: FalkorClient, case) -> None:
    ig.ensure_schema(client, case.graph)
    fid = ig.finding_id(case, QUARTER)
    client.query(
        case.graph,
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


def test_why_returns_the_quote_and_the_source_link(case):
    client = FalkorClient()
    _build(client, case)
    out = why_mod.run_why(client, case, QUARTER)
    assert out["query"]["rows"] == 1
    row = out["rows"][0]
    assert row["kind"] == "Claim"
    assert row["quote"] == "it will be a while"
    assert row["link"] == why_mod.source_link("mail", MSG, None)
    assert row["link"].startswith("http") and row["link"].endswith("msg00402.html")


def test_why_query_is_the_guarded_read_with_a_timeout(case):
    client = FalkorClient()
    _build(client, case)
    out = why_mod.run_why(client, case, QUARTER)
    assert out["query"]["timeout_ms"] > 0
    assert out["query"]["guard"].startswith("GRAPH.RO_QUERY")
    assert "LIMIT 200" in out["query"]["cypher"]
