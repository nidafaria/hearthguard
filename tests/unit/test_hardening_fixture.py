"""Hardening simulator on fixture graphs. Real FalkorDB, no mocks (docs/HEARTHGUARD.md 8.5)."""

import uuid

import pytest

from core.graph.client import FalkorClient
from core.hardening import simulate as sim

FIXTURES = sim.DEFAULT_FIXTURES


@pytest.fixture(scope="module")
def client() -> FalkorClient:
    return FalkorClient()


def graph_names(client: FalkorClient) -> set[str]:
    return {
        g if isinstance(g, str) else g.decode() for g in client.db.execute_command("GRAPH.LIST")
    }


@pytest.mark.parametrize("fixture", FIXTURES)
@pytest.mark.parametrize("step", sim.STEPS)
def test_original_graph_is_unchanged(client, fixture, step):
    r = sim.simulate(fixture, step, client)
    assert r["original_counts_before"] == r["original_counts_after"]


@pytest.mark.parametrize("fixture", FIXTURES)
def test_add_keeper_changes_only_the_copy(client, fixture):
    r = sim.simulate(fixture, sim.STEP_ADD_KEEPER, client)
    orig, hard = r["original_counts_before"], r["hardened_copy_counts"]
    assert hard["nodes"] == orig["nodes"] + 1
    assert hard["edges"] == orig["edges"] + 1
    assert r["original_counts_after"] == orig
    assert r["after"]["guardians"] == r["before"]["guardians"] + 1


@pytest.mark.parametrize("fixture", FIXTURES)
def test_two_approvals_never_lowers_cost(client, fixture):
    r = sim.simulate(fixture, sim.STEP_TWO_APPROVALS, client)
    assert r["after"]["cost"] >= r["before"]["cost"]
    assert r["after"]["cost"] >= 2


def test_no_graphs_left_behind(client):
    # A run id unique to this test: only the graphs named with it are checked and dropped.
    run = f"tstfx{uuid.uuid4().hex[:8]}"
    mine = (f"org_hf{run}", f"org_hfa{run}", f"harden_{run}")
    try:
        sim.simulate(FIXTURES[0], sim.STEP_ADD_KEEPER, client, run=run)
        assert not set(mine) & graph_names(client)
    finally:
        for g in mine:
            client.drop(g)


def test_unknown_step_and_fixture(client):
    with pytest.raises(KeyError):
        sim.simulate("nope", sim.STEP_ADD_KEEPER, client)
    with pytest.raises(ValueError):
        sim.simulate(FIXTURES[0], "nope", client)
