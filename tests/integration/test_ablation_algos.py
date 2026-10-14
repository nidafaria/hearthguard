"""Algorithm ablation (spec §10.2): Vouch components, SPpaths and maxFlow off one at a time.

Hand-worked expectations:
  - vouch_without_graph: two low-history vouchers for one candidate fire it with no SHARES edge at
    all (the frozen Vouch says NOT_COMPUTED there); one voucher does not fire it.
  - keeper_count_guardians: b_two_keepers has two keepers who can grant -> 2 (the same as the
    maxFlow cut there); a_single_chain -> 1.
  - sppaths_off: the decision path never calls takeover cost or trust path, so the stub counts 0 and
    every decision is identical to the baseline.
  - the real org graph is unchanged and no scratch graph is left behind.
"""

import json
import uuid
from pathlib import Path

import pytest

from core.detectors import vouch
from core.graph.client import FalkorClient
from core.takeover import guardians
from eval import ablation_algos as aa
from tests.fixtures.takeover_cases import CASES

REAL = "tallowdate"
SAVED = Path(__file__).resolve().parents[2] / "eval" / "results" / "ablation_algos.json"
T = 1_000_000


def _graphs(client):
    return {
        g if isinstance(g, str) else g.decode() for g in client.db.execute_command("GRAPH.LIST")
    }


def _case(name):
    return next(c for c in CASES if c.name == name)


def test_guardians_without_maxflow_counts_keepers(client):
    for name, expected in (("b_two_keepers", 2), ("a_single_chain", 1)):
        org = "alg" + uuid.uuid4().hex[:8]
        g = f"org_{org}"
        client.drop(g)
        try:
            case = _case(name)
            case.build(client, g)
            r = aa.keeper_count_guardians(client, org, "release", case.T)
            assert (r.status, r.guardians) == (guardians.COMPUTED, expected)
        finally:
            client.drop(g)


@pytest.fixture
def vouch_org(client):
    org = "alg" + uuid.uuid4().hex[:8]
    g = f"org_{org}"
    client.drop(g)

    def q(cypher, params=None):
        client.query(g, cypher, params or {}, timeout_ms=30_000)

    for h in ("cand", "v1", "v2"):
        q("MERGE (:Actor {hid: $h, kind: 'human', first_seen_in_org: 999000})", {"h": h})
    for v in ("v1", "v2"):
        q(
            "MATCH (a:Actor {hid: $h}) CREATE (a)-[:ASSERTED]->"
            "(:Claim {id: $c, kind: 'VOUCH', at: 999600, target_hid: 'cand'})",
            {"h": v, "c": "c" + v},
        )
        q(
            "MATCH (a:Actor {hid: $h}) CREATE (a)-[:DID {at: 999700}]->"
            "(:Action {ref: $r, kind: 'commit', at: 999700})",
            {"h": v, "r": "r" + v},
        )
    yield org
    client.drop(g)


def test_vouch_without_graph_fires_on_two_vouchers_and_frozen_vouch_does_not(client, vouch_org):
    ablated = aa.vouch_without_graph(client, vouch_org, T)
    frozen = vouch.vouch(client, vouch_org, T)
    assert ablated.status == "FIRED"
    assert frozen.status == "NOT_COMPUTED"  # no SHARES edges built: the frozen rule cannot say


def test_vouch_without_graph_needs_two_vouchers(client, vouch_org):
    client.query(
        f"org_{vouch_org}",
        "MATCH (:Actor {hid: 'v2'})-[:ASSERTED]->(c:Claim) DETACH DELETE c",
        timeout_ms=30_000,
    )
    assert aa.vouch_without_graph(client, vouch_org, T).status == "NOT_FIRED"


@pytest.fixture(scope="module")
def tclient():
    c = FalkorClient()
    if f"org_{REAL}" not in _graphs(c):
        pytest.skip("org_tallowdate is not loaded (make tallowdate-run)")
    return c


@pytest.fixture(scope="module")
def doc(tclient):
    return aa.run_ablation(REAL, 5, 7, 2, tclient)


def test_sppaths_is_not_called_by_the_decision_path(doc):
    arm = doc["arms"]["sppaths_off"]
    assert arm["stub_calls"] == {"takeover_cost": 0, "trust_path": 0}
    same = arm["decisions_equal_baseline"]
    assert same["campaigns_identical"] == same["of"]
    assert arm["versus_baseline"]["verdict"] == "tied with baseline"


def test_arms_and_accounting(doc):
    assert set(doc["arms"]) == set(aa.ARMS)
    for arm in doc["arms"].values():
        s = arm["attack"]
        assert s["n"] == 5 and s["caught"] + s["missed"] == 5
        assert arm["clean"]["n"] == 2
    assert "versus_baseline" not in doc["arms"]["baseline"]


def test_real_graph_unchanged_and_no_scratch_left(tclient, doc):
    assert doc["real_graph"]["unchanged"] is True
    left = {n for n in _graphs(tclient) if n.startswith(("org_rt", "redteam_", "takeover_"))}
    assert left == set()


def test_compare_words():
    base = {
        "attack": {"detection_rate": 0.8, "median_lead_time_days": 4.0},
        "clean": {"false_alarm_rate": 0.0},
    }
    assert aa.compare(base, base)["verdict"] == "tied with baseline"
    worse = {
        "attack": {"detection_rate": 0.6, "median_lead_time_days": 4.0},
        "clean": {"false_alarm_rate": 0.1},
    }
    assert aa.compare(base, worse)["verdict"] == "lower detection, more false alarms than baseline"


def test_saved_result_is_consistent():
    if not SAVED.exists():
        pytest.skip("eval/results/ablation_algos.json not built (python -m eval.ablation_algos)")
    d = json.loads(SAVED.read_text(encoding="utf-8"))
    assert d["real_graph"]["unchanged"] is True
    assert d["arms"]["sppaths_off"]["stub_calls"] == {"takeover_cost": 0, "trust_path": 0}
    for name, arm in d["arms"].items():
        if name != "baseline":
            assert arm["versus_baseline"] == aa.compare(d["arms"]["baseline"], arm)
