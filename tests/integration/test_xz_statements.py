"""xz grant statements go into a COPY of org_xz, never the real graph; loading twice is stable."""

import pytest

from core.takeover import cost, guardians
from packs.oss import xz_statements as xs

pytestmark = pytest.mark.skipif(
    not (xs.CACHE / "swtch.html").exists(), reason="statement pages are not cached"
)

COPY = "xz_statements_test"


def _counts(client):
    g = f"org_{COPY}"
    nodes = client.query(g, "MATCH (n) RETURN count(n)", timeout_ms=30_000).result_set[0][0]
    edges = client.query(g, "MATCH ()-[r]->() RETURN count(r)", timeout_ms=30_000).result_set[0][0]
    grants = client.query(
        g,
        "MATCH ()-[r:GRANTED|CAN_GRANT]->() RETURN type(r), count(r) ORDER BY type(r)",
        timeout_ms=30_000,
    ).result_set
    return nodes, edges, grants


def test_statements_load_twice_gives_identical_counts(client):
    stmts = xs.build_statements()
    g = f"org_{COPY}"
    try:
        client.drop(g)
        client.query(g, "CREATE (:Org {id: 'x'})", timeout_ms=30_000)
        first = None
        for _ in range(2):
            from packs.oss import grants

            grants.write_records(client, g, xs.to_records(stmts))
            now = _counts(client)
            first = first or now
            assert now == first
        assert first[2] == [["CAN_GRANT", 2], ["GRANTED", 3]]
    finally:
        client.drop(g)


def test_statements_have_short_quotes_and_no_names():
    stmts = xs.build_statements()
    assert len(stmts) == 9
    for s in stmts:
        assert len(s["quote"].split()) < 15
        assert len(s["actor"]) == 64
        assert isinstance(s["date_approximate"], bool)
    assert {s["edge"] for s in stmts} == {None, "grant", "can_grant"}


def test_copy_is_computed_and_real_graph_untouched(client):
    stmts = xs.build_statements()
    g = f"org_{COPY}"
    if "org_xz" not in client.db.list_graphs():
        pytest.skip("org_xz is not ingested on this database")
    before = client.query("org_xz", "MATCH (p:Privilege) RETURN count(p)", timeout_ms=30_000)
    try:
        xs.load_into_copy(client, "org_xz", g, stmts)
        T = xs.unix_of("2024-03-31")
        c = cost.takeover_cost(client, COPY, "release", T)
        gd = guardians.guardians(client, COPY, "release", T)
        assert c.status == cost.COMPUTED and gd.status == guardians.COMPUTED
    finally:
        client.drop(g)
    after = client.query("org_xz", "MATCH (p:Privilege) RETURN count(p)", timeout_ms=30_000)
    assert before.result_set == after.result_set == [[0]]
