"""hearthguard-core MCP server (spec §12.1): the nine tools on a real FalkorDB. No mocks.

Hand-worked graph (T = 1_000_000; org built from the b_two_keepers fixture):
  keepers A (CAN_GRANT release, 1 approval, at 100) and B (CAN_GRANT release, 2 approvals, at 200)
    -> takeover cost 1 (win A alone), guardians 2 (a cut needs both).
  newbie N: first seen at 990_000 s, one DID action, vouched for by two accounts.
  claims: N asserted a PRESSURE claim at 995_000 and an old one at 100.
  Normal: active_keepers = 2, computed at 900_000.
Expected: cost 1; guardians 2; N is low-history; claims_for with a 90-day window returns both
claims, with a 1-day window (86_400 s) the one at 995_000 only; add_second_keeper raises guardians
from 2 to 3 on a copy and leaves the org graph as it was.
"""

import asyncio
import importlib.util
import uuid
from pathlib import Path

import pytest

from core.graph.hashing import identifier_hash
from tests.fixtures.takeover_cases import CASES

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "mcp_servers" / "hearthguard-core" / "server.py"
FIXTURE = next(c for c in CASES if c.name == "b_two_keepers")
T = 1_000_000


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tools = _load(ROOT / "mcp_servers" / "hearthguard-core" / "tools.py", "hg_core_tools_test")


def _graphs(client) -> set[str]:
    return {
        g if isinstance(g, str) else g.decode() for g in client.db.execute_command("GRAPH.LIST")
    }


@pytest.fixture
def org(client):
    org = "mcp" + uuid.uuid4().hex[:8]
    g = f"org_{org}"
    client.drop(g)
    FIXTURE.build(client, g)

    def q(cypher, params=None):
        return client.query(g, cypher, params or {}, timeout_ms=30_000)

    n = identifier_hash("newbie@example.invalid")
    v1, v2 = identifier_hash("v1@example.invalid"), identifier_hash("v2@example.invalid")
    for hid in (n, v1, v2):
        q("MERGE (:Actor {hid: $h, kind: 'human', first_seen_in_org: 990000})", {"h": hid})
    q(
        "MATCH (a:Actor {hid: $h}) "
        "CREATE (a)-[:DID {at: 991000}]->(:Action {ref: 'x1', kind: 'commit', at: 991000})",
        {"h": n},
    )
    for cid, at in (("c-new", 995000), ("c-old", 100)):
        q(
            "MATCH (a:Actor {hid: $h}) "
            "CREATE (a)-[:ASSERTED]->(:Claim {id: $c, kind: 'PRESSURE', at: $at})",
            {"h": n, "c": cid, "at": at},
        )
    for v, cid in ((v1, "v-1"), (v2, "v-2")):
        q(
            "MATCH (a:Actor {hid: $h}) CREATE (a)-[:ASSERTED]->"
            "(:Claim {id: $c, kind: 'VOUCH', at: 996000, target_hid: $t})",
            {"h": v, "c": cid, "t": n},
        )
    q(
        "CREATE (:Normal {metric: 'active_keepers', scope: 'org', window: '90d', "
        "computed_at: 900000, value: 2})"
    )
    q(
        "MATCH (a:Actor {hid: 'A'}) "
        "CREATE (a)-[:DID {at: 1000000}]->(:Action {ref: 'tick', kind: 'commit', at: 1000000})"
    )
    yield {"org": org, "newbie": "newbie@example.invalid", "nhid": n}
    client.drop(g)


def test_takeover_cost_and_guardians(client, org):
    c = tools.takeover_cost(client, org["org"], "release", T)
    g = tools.guardians_(client, org["org"], "release", T)
    assert (c["status"], c["cost"]) == ("COMPUTED", 1)
    assert (g["status"], g["guardians"]) == ("COMPUTED", 2)
    assert c["T_defaulted"] is False


def test_default_t_is_the_newest_event(client, org):
    c = tools.takeover_cost(client, org["org"], "release")
    assert c["T_defaulted"] is True and c["T"] == T


def test_org_normal_returns_the_metric(client, org):
    r = tools.org_normal(client, org["org"], T)
    assert r["found"] is True
    assert r["metrics"] == [
        {
            "metric": "active_keepers",
            "scope": "org",
            "window": "90d",
            "computed_at": 900000,
            "value": 2,
        }
    ]


def test_org_normal_is_as_of_T(client, org):
    assert tools.org_normal(client, org["org"], 800_000)["found"] is False


def test_claims_for_window(client, org):
    wide = tools.claims_for(client, org["org"], org["newbie"], 90, T)
    assert [c["claim_id"] for c in wide["claims"]] == ["c-old", "c-new"]
    narrow = tools.claims_for(client, org["org"], org["newbie"], 1, T)
    assert [c["claim_id"] for c in narrow["claims"]] == ["c-new"]
    assert narrow["actor_hid"] == org["nhid"]


def test_check_trust_is_evidence_not_a_verdict(client, org):
    r = tools.check_trust(client, org["org"], org["newbie"], "release", T)
    assert r["history"]["status"] == "COMPUTED"
    assert r["history"]["low_history"] is True
    assert len(r["vouched_for_by"]) == 2
    assert r["already_holds"] == []
    assert r["actor_hid"] == org["nhid"]
    assert "score" not in r and "verdict" not in r
    assert org["newbie"] not in str(r)  # the raw identifier is never echoed


def test_trust_path_returns_a_status(client, org):
    r = tools.trust_path_(client, org["org"], org["newbie"], "release", T)
    assert r["status"] in ("NO PATH", "COMPUTED")
    assert r["actor_hid"] == org["nhid"]


def test_simulate_hardening_adds_a_guardian_on_a_copy(client, org):
    r = tools.simulate_hardening(client, org["org"], "add_second_keeper", T)
    assert r["before"]["guardians"] == 2
    assert r["after"]["guardians"] == 3
    assert r["changed_anything"] is True
    assert tools.guardians_(client, org["org"], "release", T)["guardians"] == 2
    left = {n for n in _graphs(client) if n.startswith(("harden_", "org_hsm", "takeover_"))}
    assert left == set() or all(org["org"] not in n for n in left)


def test_simulate_hardening_rejects_an_unknown_step(client, org):
    with pytest.raises(ValueError):
        tools.simulate_hardening(client, org["org"], "make_it_safe", T)


def test_tools_do_not_write_to_the_org_graph(client, org):
    g = f"org_{org['org']}"

    def fingerprint():
        n = client.query(g, "MATCH (n) RETURN count(n)", timeout_ms=30_000).result_set[0][0]
        e = client.query(g, "MATCH ()-[r]->() RETURN count(r)", timeout_ms=30_000).result_set[0][0]
        return n, e

    before = fingerprint()
    o, a = org["org"], org["newbie"]
    tools.takeover_cost(client, o, "release", T)
    tools.guardians_(client, o, "release", T)
    tools.org_normal(client, o, T)
    tools.trust_path_(client, o, a, "release", T)
    tools.claims_for(client, o, a, 90, T)
    tools.check_trust(client, o, a, "release", T)
    tools.simulate_hardening(client, o, "require_two_approvals", T)
    assert fingerprint() == before


def test_why_unknown_case_and_unknown_finding(client):
    assert tools.why(client, "nope:2024-Q1")["found"] is False
    if "org_tallowdate" in _graphs(client):
        r = tools.why(client, "tallowdate:no-such-quarter")
        assert r["found"] is False and r["query"]["timeout_ms"] > 0


def test_visibility_gaps_reads_the_saved_run():
    r = tools.visibility_gaps("oss-fuzz-build-change-pr10667")
    assert r["found"] is True and r["status"] == "COMPUTED"
    assert {g["gap"] for g in r["gaps"]} <= {"UNREACHABLE", "UNNOTICED"}
    miss = tools.visibility_gaps("not-a-decision")
    assert miss["found"] is False
    assert "oss-fuzz-build-change-pr10667" in miss["known_decisions"]


def test_the_server_registers_exactly_the_nine_spec_tools():
    mod = _load(SERVER, "hearthguard_core_server_test")
    listed = asyncio.run(mod.server.list_tools())
    names = sorted(t.name for t in getattr(listed, "tools", listed))
    assert names == sorted(
        [
            "check_trust",
            "takeover_cost",
            "guardians",
            "org_normal",
            "trust_path",
            "visibility_gaps",
            "simulate_hardening",
            "why",
            "claims_for",
        ]
    )
