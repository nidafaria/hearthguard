"""pack-oss MCP server (spec §12.1): the four tools on a real FalkorDB. No mocks.

Hand-worked expectations:
  - tallowdate release tallowdate-0155 went through git with 2 approvers and no CI provenance
    (eval/results/tallowdate_load.json release_path); release_path reports that path.
  - a scratch org with GRANTED edges: grant_history lists them in time order, and only those at or
    before T.
  - a scratch ecosystem graph: identity I1 emits in places P1 and P2, I2 only in P1, I3 only in P2.
    identities_by_number_of_places = {1: 2, 2: 1}; in_more_than_one_place = 1.
  - upstream_context for a package with no release of that version says found false for the
    release path and still returns the takeover parts, each with its own status.
"""

import asyncio
import importlib.util
import uuid
from pathlib import Path

import pytest

from tests.fixtures.takeover_cases import CASES

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = next(c for c in CASES if c.name == "b_two_keepers")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tools = _load(ROOT / "mcp_servers" / "pack-oss" / "tools.py", "pack_oss_tools_test")


def _graphs(client) -> set[str]:
    return {
        g if isinstance(g, str) else g.decode() for g in client.db.execute_command("GRAPH.LIST")
    }


@pytest.fixture
def org(client):
    org = "oss" + uuid.uuid4().hex[:8]
    g = f"org_{org}"
    client.drop(g)
    FIXTURE.build(client, g)
    client.query(
        g,
        "MERGE (a:Actor {hid: 'G1'}) WITH a MATCH (p:Privilege {kind: 'release'}) "
        "CREATE (a)-[:GRANTED {at: 500}]->(p)",
        timeout_ms=30_000,
    )
    client.query(
        g,
        "MERGE (a:Actor {hid: 'G2'}) WITH a MATCH (p:Privilege {kind: 'release'}) "
        "CREATE (a)-[:GRANTED {at: 900}]->(p)",
        timeout_ms=30_000,
    )
    yield org
    client.drop(g)


def test_grant_history_is_in_time_order_and_as_of_T(client, org):
    r = tools.grant_history(client, org, 600)
    assert [(x["actor_hid"], x["at"]) for x in r["grants"]] == [("G1", 500)]
    r = tools.grant_history(client, org, 1000)
    assert [(x["actor_hid"], x["at"]) for x in r["grants"]] == [("G1", 500), ("G2", 900)]


def test_grant_history_empty_says_none_documented(client):
    g = "org_oss" + uuid.uuid4().hex[:8]
    client.drop(g)
    try:
        client.query(g, "CREATE (:Action {ref: 'a', kind: 'commit', at: 10})", timeout_ms=30_000)
        r = tools.grant_history(client, g.removeprefix("org_"))
        assert r["grants"] == [] and "none are documented" in r["note"]
    finally:
        client.drop(g)


def test_ecosystem_overlap_counts_identities_by_places(client):
    eco = "tst" + uuid.uuid4().hex[:8]
    g = f"ecosystem_{eco}"
    client.drop(g)
    try:

        def q(cypher):
            client.query(g, cypher, timeout_ms=30_000)

        q("CREATE (:Place {ref: 'P1', kind: 'repo'}), (:Place {ref: 'P2', kind: 'list'})")
        for i, places in (("I1", ("P1", "P2")), ("I2", ("P1",)), ("I3", ("P2",))):
            q(f"CREATE (:Identity {{hid: '{i}'}})")
            for n, p in enumerate(places):
                q(
                    f"MATCH (i:Identity {{hid: '{i}'}}), (pl:Place {{ref: '{p}'}}) "
                    f"CREATE (i)-[:EMITTED]->(:Signal {{ref: '{i}{n}'}})-[:RECORDED_IN]->(pl)"
                )
        r = tools.ecosystem_overlap(client, eco)
        assert r["found"] is True
        assert r["identities"] == 3
        assert r["identities_by_number_of_places"] == {1: 2, 2: 1}
        assert r["in_more_than_one_place"] == 1
        assert [p["ref"] for p in r["places"]] == ["P1", "P2"]
    finally:
        client.drop(g)
    assert tools.ecosystem_overlap(client, "no-such-eco")["found"] is False


def test_release_path_reports_the_tallowdate_release(client):
    if "org_tallowdate" not in _graphs(client):
        pytest.skip("org_tallowdate is not loaded (make tallowdate-run)")
    r = tools.release_path(client, "tallowdate", "tallowdate-0155")
    assert r["found"] is True
    assert r["path"]["channel"] == "git" and r["path"]["approvers"] == 2
    assert r["versus_normal"]["status"] in ("FIRED", "NOT_FIRED", "NOT_COMPUTED")
    miss = tools.release_path(client, "tallowdate", "v0.0.0-nope")
    assert miss["found"] is False


def test_upstream_context_answers_in_parts(client, org):
    r = tools.upstream_context(client, org, "v9.9.9")
    assert r["release_path"]["found"] is False
    assert r["takeover_cost"]["status"] == "COMPUTED" and r["takeover_cost"]["cost"] == 1
    assert r["guardians"]["status"] == "COMPUTED" and r["guardians"]["guardians"] == 2


def test_the_tools_are_read_only(client, org):
    g = f"org_{org}"

    def fingerprint():
        n = client.query(g, "MATCH (n) RETURN count(n)", timeout_ms=30_000).result_set[0][0]
        e = client.query(g, "MATCH ()-[r]->() RETURN count(r)", timeout_ms=30_000).result_set[0][0]
        return n, e

    before = fingerprint()
    tools.grant_history(client, org)
    tools.release_path(client, org, "v1")
    tools.upstream_context(client, org, "v1")
    assert fingerprint() == before


def test_the_server_registers_exactly_the_four_spec_tools():
    mod = _load(ROOT / "mcp_servers" / "pack-oss" / "server.py", "pack_oss_server_test")
    listed = asyncio.run(mod.server.list_tools())
    names = sorted(t.name for t in getattr(listed, "tools", listed))
    assert names == ["ecosystem_overlap", "grant_history", "release_path", "upstream_context"]
