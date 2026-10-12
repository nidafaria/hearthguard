"""Hardening on a real FalkorDB copy of org_xz, and on a grant-bearing org. No mocks."""

import json
import uuid
from pathlib import Path

import pytest

from core.graph.client import FalkorClient
from core.hardening import simulate as sim
from core.hardening import xz
from tests.fixtures.takeover_cases import CASES

NOT_COMPUTED = "NOT COMPUTED"
T = 1711929599


@pytest.fixture(scope="module")
def client() -> FalkorClient:
    return FalkorClient()


def names(client: FalkorClient) -> set[str]:
    return {
        g if isinstance(g, str) else g.decode() for g in client.db.execute_command("GRAPH.LIST")
    }


@pytest.fixture(scope="module")
def xz_ready(client):
    if "org_xz" not in names(client) or sim.counts(client, "org_xz")["nodes"] == 0:
        pytest.skip("org_xz is not loaded (make ingest-xz)")


@pytest.mark.parametrize("step", sim.MENU)
def test_xz_step_is_not_computed_and_org_unchanged(client, xz_ready, step):
    before = sim.counts(client, "org_xz")
    r = xz.harden_org(client, "xz", step, T)
    assert sim.counts(client, "org_xz") == before
    assert r["copy_counts"] == before
    for side in ("before", "after"):
        for part in ("takeover_cost", "guardians"):
            assert r[side][part]["status"] == NOT_COMPUTED
            assert r[side][part]["value"] is None


def test_xz_grant_steps_find_nothing_to_change(client, xz_ready):
    for step in (sim.STEP_ADD_KEEPER, sim.STEP_TWO_APPROVALS):
        r = xz.harden_org(client, "xz", step, T)
        assert r["applied"] is False
        assert r["note"]


def test_provenance_step_changes_the_copy_not_org_xz(client, xz_ready):
    r = xz.harden_org(client, "xz", sim.STEP_PROVENANCE, T)
    assert r["applied"] is True
    res = client.query(
        "org_xz", "MATCH (n:Normal) WHERE n.provenance_required IS NOT NULL RETURN 1"
    )
    assert res.result_set == []


def test_no_graphs_left_behind(client, xz_ready):
    # A run id unique to this test: only the graphs named with it are checked and dropped.
    run = f"tstxz{uuid.uuid4().hex[:8]}"
    mine = (f"harden_{run}", f"org_hza{run}")
    try:
        xz.harden_org(client, "xz", sim.STEP_ADD_KEEPER, T, run=run)
        assert not set(mine) & names(client)
    finally:
        for g in mine:
            client.drop(g)


def test_same_path_computes_on_a_grant_bearing_org(client):
    case = next(c for c in CASES if c.name == "a_single_chain")
    client.drop("org_hzt")
    case.build(client, "org_hzt")
    try:
        r = xz.harden_org(client, "hzt", sim.STEP_ADD_KEEPER, case.T)
    finally:
        client.drop("org_hzt")
    assert r["applied"] is True
    assert r["before"]["guardians"]["value"] == 1
    assert r["after"]["guardians"]["value"] == 2


def test_saved_file_has_no_invented_values():
    path = Path(xz.OUT)
    if not path.exists():
        pytest.skip("run make harden-xz first")
    d = json.loads(path.read_text(encoding="utf-8"))
    assert d["org_counts_before"] == d["org_counts_after"]
    assert len(d["results"]) == 10
    for q in d["results"]:
        assert [s["step"] for s in q["steps"]] == list(sim.MENU)
        for s in q["steps"]:
            for side in ("before", "after"):
                for part in s[side].values():
                    if part["status"] == NOT_COMPUTED:
                        assert part["value"] is None
