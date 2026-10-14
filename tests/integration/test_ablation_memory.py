"""Memory ablation (spec §10.2): full memory against forgetful memory, on a real FalkorDB.

Hand-worked expectations:
  - delta()/verdict(): arm 0.6 vs full 0.9 detection is -0.3 -> "worse"; equal rates and equal lead
    -> "tied"; equal rates and lead 2 days shorter -> "same detection rate, shorter lead time";
    a missing rate -> "not computed". No rounding into a tie.
  - the `full` arm is the same scoring as `make redteam`: same campaigns, same summary.
  - caught + missed = n in every arm; the real org graph is unchanged by a run.
  - the saved eval/results/ablation_memory.json agrees with its own rows.
"""

import json
from pathlib import Path

import pytest

from core.graph.client import FalkorClient
from eval import ablation_memory as am
from redteam import run

REAL = "tallowdate"
SAVED = Path(__file__).resolve().parents[2] / "eval" / "results" / "ablation_memory.json"


def _graphs(client):
    return {
        g if isinstance(g, str) else g.decode() for g in client.db.execute_command("GRAPH.LIST")
    }


def test_verdict_words():
    assert am.verdict(am.delta({"detection_rate": 0.9}, {"detection_rate": 0.6})).startswith(
        "worse"
    )
    assert am.verdict(am.delta({"detection_rate": 0.9}, {"detection_rate": 0.95})).startswith(
        "better"
    )
    tie = am.delta(
        {"detection_rate": 0.9, "median_lead_time_days": 5.0},
        {"detection_rate": 0.9, "median_lead_time_days": 5.0},
    )
    assert am.verdict(tie) == "tied with full memory"
    shorter = am.delta(
        {"detection_rate": 0.9, "median_lead_time_days": 5.0},
        {"detection_rate": 0.9, "median_lead_time_days": 3.0},
    )
    assert am.verdict(shorter) == "same detection rate, shorter lead time"
    assert am.verdict(am.delta({"detection_rate": None}, {"detection_rate": 0.5})) == "not computed"


@pytest.fixture(scope="module")
def tclient():
    c = FalkorClient()
    if f"org_{REAL}" not in _graphs(c):
        pytest.skip("org_tallowdate is not loaded (make tallowdate-run)")
    return c


@pytest.fixture(scope="module")
def doc(tclient):
    return am.run_ablation(REAL, 5, 7, 2, tclient)


def test_every_arm_accounts_for_every_campaign(doc):
    assert set(doc["arms"]) == {"full", "forget_90", "forget_30"}
    for arm in doc["arms"].values():
        s = arm["summary"]
        assert s["n"] == 5 and s["caught"] + s["missed"] == 5
        assert arm["clean"]["n"] == 2


def test_the_real_graph_is_unchanged_and_nothing_is_left_behind(tclient, doc):
    assert doc["real_graph"]["unchanged"] is True
    left = {n for n in _graphs(tclient) if n.startswith(("org_rt", "redteam_", "takeover_"))}
    assert left == set()


def test_full_arm_matches_the_redteam_run(tclient, doc):
    base = run.run_redteam(REAL, 5, 7, tclient)["summary"]
    assert doc["arms"]["full"]["summary"] == base


def test_comparison_is_computed_from_the_arm_rows(doc):
    for name, c in doc["comparison"].items():
        expect = am.delta(doc["arms"]["full"]["summary"], doc["arms"][name]["summary"])
        assert c["overall"]["delta"] == expect
        assert c["overall"]["verdict"] == am.verdict(expect)


def test_saved_result_agrees_with_its_own_rows():
    if not SAVED.exists():
        pytest.skip("eval/results/ablation_memory.json not built (python -m eval.ablation_memory)")
    d = json.loads(SAVED.read_text(encoding="utf-8"))
    assert d["real_graph"]["unchanged"] is True
    for name, arm in d["arms"].items():
        assert sum(r["n"] for r in arm["by_patience"]) == arm["summary"]["n"] == d["n"]
        assert arm["summary"]["caught"] == sum(r["caught"] for r in arm["by_patience"])
        if name != "full":
            expect = am.delta(d["arms"]["full"]["summary"], arm["summary"])
            assert d["comparison"][name]["overall"]["delta"] == expect
