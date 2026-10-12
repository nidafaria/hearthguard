"""Rush, Bypass and Lone keeper on hand-built graphs and on real org_xz. Real FalkorDB, no mocks.

Expected results are derived by hand in tests/fixtures/detector_cases.py. If a result differs from
its derivation, the detector is wrong, not the expected value.
"""

import json

import pytest

from core.detectors import bypass, lone_keeper, rush
from core.detectors.common import FIRED, NOT_COMPUTED, NOT_FIRED
from core.graph.as_of import MissingAsOfError
from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient
from core.takeover import scratch as sc
from eval import xz_detector_status
from packs.oss import xz_graph
from tests.fixtures.detector_cases import (
    BYPASS_CASES,
    LONE_CASES,
    PRIV,
    RUSH_CASES,
    RUSH_E_LATER,
    BypassCase,
    LoneCase,
    RushCase,
    T,
)


class RecordingClient(FalkorClient):
    """The real client, noting the name of every graph written through client.query."""

    def __init__(self) -> None:
        super().__init__()
        self.written: list[str] = []

    def query(self, name, cypher, params=None, *, timeout_ms=DEFAULT_TIMEOUT_MS):
        self.written.append(name)
        return super().query(name, cypher, params, timeout_ms=timeout_ms)


@pytest.fixture(scope="module")
def client() -> FalkorClient:
    return FalkorClient()


def graph_names(client: FalkorClient) -> set[str]:
    return {
        g if isinstance(g, str) else g.decode() for g in client.db.execute_command("GRAPH.LIST")
    }


@pytest.fixture
def org(client, request):
    org = "dt_" + request.node.name.split("[")[0].removeprefix("test_")[:30]
    client.drop(sc.graph_for(org))
    yield org
    client.drop(sc.graph_for(org))


def build(client: FalkorClient, org: str, case) -> None:
    client.drop(sc.graph_for(org))
    case.build(client, sc.graph_for(org))


def check_rush(res, case: RushCase) -> None:
    assert res.status == case.status
    assert case.reason_contains in res.reason
    if case.days is not None:
        ev = res.evidence
        assert ev["days"] == pytest.approx(case.days, abs=1e-3)
        assert ev["threshold_days"] == pytest.approx(case.threshold, abs=1e-3)
        assert ev["rule"] == case.rule
        assert ev["n_history"] == case.n_history
        assert len(ev["grant_id_hash"]) == 64


# ------------------------------------------------------------------ Rush
@pytest.mark.parametrize("case", RUSH_CASES, ids=lambda c: c.name)
def test_rush_fixture(client, org, case):
    build(client, org, case)
    res = rush.rush(client, org, PRIV, case.actor, case.T)
    print(f"\n[rush {case.name}] {res.status}: {res.reason}")
    check_rush(res, case)
    assert res.queries and res.query_ms is not None
    assert all(q["query"] and q["ms"] >= 0 for q in res.queries)


def test_rush_a_grant_is_the_hash_of_hashed_parts_only(client, org):
    build(client, org, RUSH_CASES[0])
    ev = rush.rush(client, org, PRIV, "S", T).evidence
    assert ev["grant_id_hash"] == rush.grant_id_hash("S", PRIV, 2020 * 86_400)
    assert "S" not in json.dumps({k: v for k, v in ev.items() if k != "grant_id_hash"})


def test_rush_future_grant_changes_the_answer_only_once_T_reaches_it(client, org):
    build(client, org, RUSH_CASES[4])
    at_T = rush.rush(client, org, PRIV, "S", T)
    at_later = rush.rush(client, org, PRIV, "S", RUSH_E_LATER.T)
    assert (at_T.status, at_T.evidence["n_history"]) == (FIRED, 5)
    check_rush(at_later, RUSH_E_LATER)


def test_rush_undated_grant_reports_how_many(client, org):
    build(client, org, RUSH_CASES[3])
    res = rush.rush(client, org, PRIV, "S", T)
    assert res.evidence == {"grants_without_timestamp": 1}


def test_percentile_formula_by_hand():
    # 1..10: h = 9 * 0.10 = 0.9, so 1 + 0.9 * (2 - 1) = 1.9.
    assert rush.percentile_cont(list(range(1, 11)), 0.10) == pytest.approx(1.9)
    assert rush.percentile_cont([100.0] * 10, 0.10) == 100.0
    # Equal to the threshold is not below it.
    assert rush.decide(100.0, [100.0] * 10)[0] is False
    assert rush.decide(99.9999, [100.0] * 10)[0] is True
    # Four grants: fallback. Five grants: the org's own percentile.
    assert rush.decide(10.0, [1000.0] * 4)[2] == "fallback_180d"
    assert rush.decide(10.0, [1000.0] * 5)[2] == "org_p10"


def test_rush_without_privilege_is_not_computed(client, org):
    client.query(sc.graph_for(org), "CREATE (:Actor {hid: 'S'})")
    res = rush.rush(client, org, PRIV, "S", T)
    assert res.status == NOT_COMPUTED and "no grant data" in res.reason


# ------------------------------------------------------------------ Bypass
@pytest.mark.parametrize("case", BYPASS_CASES, ids=lambda c: c.name)
def test_bypass_fixture(client, org, case: BypassCase):
    build(client, org, case)
    res = bypass.bypass(client, org, "new", case.T)
    print(f"\n[bypass {case.name}] {res.status}: {res.reason}")
    assert res.status == case.status
    if case.reason_contains:
        assert case.reason_contains in res.reason
    if case.differing:
        assert res.evidence["differing"] == list(case.differing)
    elif "properties" in res.evidence:
        assert res.evidence["differing"] == []
    if case.not_computed:
        assert sorted(res.evidence["not_computed_properties"]) == sorted(case.not_computed)
    for prop, status in case.prop_status.items():
        assert res.evidence["properties"][prop]["status"] == status
    assert res.queries and res.query_ms is not None


def test_bypass_can_fire_alone_with_other_properties_unknown(client, org):
    # Only channel is recorded. It differs, so Bypass fires even though nothing else is known.
    case_org = sc.graph_for(org)
    client.query(case_org, "CREATE (:Org {id: 'f', pack: 'oss'})")
    for i, ch in enumerate(["ci", "ci", "ci"], start=1):
        client.query(
            case_org,
            "CREATE (:Action {ref: $r, kind: 'release', at: $at})-[:VIA]->(:Path {channel: $c})",
            {"r": f"h{i}", "at": i * 86_400, "c": ch},
        )
    client.query(
        case_org,
        "CREATE (:Action {ref: 'new', kind: 'release', at: 864000})"
        "-[:VIA]->(:Path {channel: 'email'})",
    )
    res = bypass.bypass(client, org, "new", 2_000_000)
    assert res.status == FIRED and res.evidence["differing"] == ["channel"]
    assert len(res.evidence["not_computed_properties"]) == 6


def test_bypass_more_approvers_than_usual_carries_a_note(client, org):
    case = BYPASS_CASES[8]
    assert case.name == "fin_more_approvers"
    build(client, org, case)
    res = bypass.bypass(client, org, "new", case.T)
    verdict = res.evidence["properties"]["approvers"]
    assert verdict["status"] == "MATCHES" and "not a bypass" in verdict["note"]


def test_bypass_judge_by_hand():
    assert bypass.judge("channel", "ci", ["ci", "ci", "email"])["status"] == "MATCHES"
    assert bypass.judge("channel", "email", ["ci", "ci", "email"])["status"] == "DIFFERS"
    assert bypass.judge("approvers", 1, [2, 2])["status"] == "DIFFERS"
    assert bypass.judge("approvers", 3, [2, 2])["status"] == "MATCHES"
    assert bypass.judge("ci", None, [True])["status"] == NOT_COMPUTED
    assert bypass.judge("ci", True, [None, None])["status"] == NOT_COMPUTED
    assert bypass.judge("channel", "ci", ["ci", "email"])["status"] == NOT_COMPUTED  # tie


# ------------------------------------------------------------------ Lone keeper
@pytest.mark.parametrize("case", LONE_CASES, ids=lambda c: c.name)
def test_lone_keeper_fixture(client, org, case: LoneCase):
    build(client, org, case)
    res = lone_keeper.lone_keeper(client, org, PRIV, case.T)
    print(f"\n[lone {case.name}] {res.status}: {res.reason}")
    assert res.status == case.status
    assert res.flag is case.flag
    assert res.multiplier_only is True
    assert res.provisional is True
    assert res.status != FIRED  # never a standalone move
    if case.guardians is not None:
        assert res.evidence["guardians"] == case.guardians
        assert res.evidence["active_keepers"] == case.active_keepers
    else:
        assert "guardians not computed" in res.reason
        assert res.evidence == {}


# ------------------------------------------------------------------ all detectors
def test_missing_T_is_refused(client):
    with pytest.raises(MissingAsOfError):
        rush.rush(client, "x", PRIV, "S", None)
    with pytest.raises(MissingAsOfError):
        bypass.bypass(client, "x", "new", None)
    with pytest.raises(MissingAsOfError):
        lone_keeper.lone_keeper(client, "x", PRIV, None)


def test_detectors_never_write_to_the_org_graph(org):
    rec = RecordingClient()
    g = sc.graph_for(org)
    RUSH_CASES[0].build(rec, g)
    before = rec.query(g, "MATCH (n) RETURN count(n)").result_set
    rec.written.clear()

    rush.rush(rec, org, PRIV, "S", T)
    assert rec.written == []

    rec.drop(g)
    BYPASS_CASES[0].build(rec, g)
    rec.written.clear()
    bypass.bypass(rec, org, "new", BYPASS_CASES[0].T)
    assert rec.written == []

    rec.drop(g)
    LONE_CASES[0].build(rec, g)
    rec.written.clear()
    lone_keeper.lone_keeper(rec, org, PRIV, LONE_CASES[0].T)
    # Lone keeper writes only to the guardians scratch graph, which is dropped afterwards.
    assert rec.written and all(n.startswith("takeover_") for n in rec.written)
    assert sc.graph_for(org) not in rec.written
    assert not [n for n in graph_names(rec) if n.startswith("takeover_")]
    rec.drop(g)
    assert before  # the first graph really had content


def test_org_graph_is_unchanged_by_a_detector_run(client, org):
    build(client, org, RUSH_CASES[0])
    g = sc.graph_for(org)
    q = "MATCH (n) RETURN labels(n)[0] AS l, count(n) ORDER BY l"
    r = "MATCH ()-[e]->() RETURN type(e) AS t, count(e) ORDER BY t"
    before = (client.query(g, q).result_set, client.query(g, r).result_set)
    rush.rush(client, org, PRIV, "S", T)
    after = (client.query(g, q).result_set, client.query(g, r).result_set)
    assert before == after


# ------------------------------------------------------------------ real xz
def test_real_xz_is_not_computed_for_all_three(client, xz_org):
    status = xz_detector_status.build_status(client)
    d = status["detectors"]
    for name in ("rush", "bypass", "lone_keeper"):
        assert d[name]["status"] == NOT_COMPUTED, name
        assert d[name]["queries"], name
    assert "no grant data" in d["rush"]["reason"]
    assert "guardians not computed" in d["lone_keeper"]["reason"]
    assert "could not be compared" in d["bypass"]["reason"]
    # Only channel and verified are recorded on a git release path.
    for absent in ("ci", "provenance", "key_hid", "publisher_in_set", "artifact_matches_tag"):
        assert absent in d["bypass"]["reason"]
    assert not any(p in d["bypass"]["reason"] for p in ("channel,", "verified,"))
    # No computed value and no hashed id anywhere in the status.
    blob = json.dumps(status)
    for key in ('"evidence"', '"days"', '"threshold_days"', '"flag"', '"guardians":'):
        assert key not in blob
    # The hashed id of the tagger Rush would have judged appears nowhere in the status.
    tagger = client.query(
        "org_xz",
        "MATCH (a:Actor)-[:DID]->(r:Action {ref: $ref}) RETURN a.hid",
        {"ref": status["action_ref"]},
    ).result_set[0][0]
    assert tagger not in blob
    nodes = xz_graph.graph_counts(client, "org_xz")["nodes"]
    assert "Privilege" not in nodes and "Flow" not in nodes


def test_real_xz_bypass_never_returns_not_fired(client, xz_org):
    row = client.query(
        "org_xz",
        "MATCH (r:Action {kind: 'release'}) WHERE r.at <= 1711929599 "
        "RETURN r.ref ORDER BY r.at DESC LIMIT 1",
    ).result_set
    res = bypass.bypass(client, "xz", row[0][0], 1711929599)
    assert res.status == NOT_COMPUTED and res.status != NOT_FIRED
    comparable = {p for p, v in res.evidence["properties"].items() if v["status"] == "MATCHES"}
    assert comparable == {"channel", "verified"}  # the computed basis, stated


def test_committed_xz_status_file_holds_no_value(xz_org):
    out = xz_detector_status.OUT
    if not out.exists():
        pytest.skip("status file not written yet (run make detectors-xz)")
    saved = json.loads(out.read_text(encoding="utf-8"))
    for d in saved["detectors"].values():
        assert d["status"] == NOT_COMPUTED and d["reason"] and d["queries"]
        assert set(d) == {"status", "reason", "queries"}
