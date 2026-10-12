"""Red-team planting and scoring on a real FalkorDB copy. No mocks of the database.

Hand-worked expectations, written before the code was run against them:
  - real graph unchanged: node and edge counts of org_tallowdate are the same before and after a
    red-team run (the planting is into copies only).
  - caught + missed = N for every run.
  - stripping synthetic/planted/campaign_id from a copy changes no detector result (the detectors
    never read those flags).
  - a step that cannot affect a campaign shows no change: a campaign with no BYPASS move gets the
    same decision whether or not a release on the normal path is added to an unrelated scaffold
    privilege.
"""

import pytest

from core.graph.client import FalkorClient
from core.hardening.simulate import counts
from redteam import generate as gen
from redteam import plant, run, score

REAL = "tallowdate"


@pytest.fixture(scope="module")
def client():
    c = FalkorClient()
    names = {g if isinstance(g, str) else g.decode() for g in c.db.execute_command("GRAPH.LIST")}
    if f"org_{REAL}" not in names:
        pytest.skip("org_tallowdate is not loaded (make tallowdate-run)")
    return c


def test_real_graph_unchanged_after_a_run(client):
    before = counts(client, f"org_{REAL}")
    doc = run.run_redteam(REAL, 6, 7, client)
    assert counts(client, f"org_{REAL}") == before
    assert doc["real_graph"]["unchanged"] is True
    assert doc["real_graph"]["counts_before"] == before


def test_caught_plus_missed_equals_n(client):
    doc = run.run_redteam(REAL, 6, 7, client)
    s = doc["summary"]
    assert s["n"] == 6
    assert s["caught"] + s["missed"] == 6
    assert len(doc["campaigns"]) == 6


def test_no_copies_left_behind(client):
    before = {
        g if isinstance(g, str) else g.decode() for g in client.db.execute_command("GRAPH.LIST")
    }
    run.run_redteam(REAL, 3, 5, client)
    after = {
        g if isinstance(g, str) else g.decode() for g in client.db.execute_command("GRAPH.LIST")
    }
    assert {g for g in after - before if g.startswith(("org_rt", "redteam_", "takeover_"))} == set()


def test_detectors_do_not_read_planted_flags(client):
    # Hand check: plant one campaign into a copy; judge it; strip the flags from the copy;
    # judge again at the same times. Every decision and every move status must be identical.
    camp = gen.generate(1, 7, REAL)[0]
    info = run.make_template(client, REAL, run.new_run_id())
    org = f"rtflag{run.new_run_id()}"
    graph = f"org_{org}"
    try:
        client.copy(info["template"], graph)
        resolved = plant.plant_campaign(client, graph, camp, plant.day0(info["e0"]))
        times = [r["at"] for r in resolved["events"] if r["move"]]
        flagged = [score.judge(client, org, camp.privilege, t, info["e0"]) for t in times]
        plant.strip_flags(client, graph)
        stripped = [score.judge(client, org, camp.privilege, t, info["e0"]) for t in times]
        assert [(p.moves, p.decision, p.lone_keeper) for p in flagged] == [
            (p.moves, p.decision, p.lone_keeper) for p in stripped
        ]
    finally:
        client.drop(graph)
        client.drop(info["template"])


def test_rush_on_a_campaign_without_rush_is_not_fired(client):
    # Hand check: a campaign whose moves are only VOUCH has no GRANTED edge to the privilege, so the
    # RUSH aggregate over grants after E0 has no entries and cannot be FIRED.
    camps = [c for c in gen.generate(40, 9, REAL) if "RUSH" not in c.moves][:1]
    info = run.make_template(client, REAL, run.new_run_id())
    try:
        outs = run.evaluate(client, info["template"], camps, info["e0"])
        for o in outs:
            for p in o.points:
                assert p["moves"]["RUSH"] == "NOT_FIRED"
    finally:
        client.drop(info["template"])
