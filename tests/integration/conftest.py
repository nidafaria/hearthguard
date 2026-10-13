"""Fixtures shared by the integration tests."""

import uuid

import pytest

from core.graph.client import FalkorClient
from packs.oss import git_ingest, xz_graph
from tests.integration.scratch_graphs import (
    FIXTURE,
    REAL_GRAPHS,
    changed_real_graphs,
    drop_owned,
    fingerprint,
    new_org_id,
    owned,
)


@pytest.fixture(scope="session")
def xz_org() -> str:
    """org_xz as `make ingest-xz` builds it. Loaded here only if it is not already there."""
    client = FalkorClient()
    names = {
        g if isinstance(g, str) else g.decode() for g in client.db.execute_command("GRAPH.LIST")
    }
    present = "org_xz" in names
    if present:
        present = xz_graph.graph_counts(client, "org_xz")["nodes"].get("Action", 0) > 0
    if not present:
        git_ingest.ensure_mirror()
        mirror = git_ingest.RAW_DIR / "xz.git"
        tags = git_ingest.read_tags(mirror)
        commits = git_ingest.read_commits(mirror, {t["target_sha"] for t in tags})
        annotated = [t["name"] for t in tags if t["kind"] == "annotated"]
        sigs = git_ingest.verify_tags(mirror, annotated)
        xz_graph.load(client, commits, tags, sigs, graph="org_xz")
    return "xz"


@pytest.fixture
def scratch_orgs():
    """Two fresh scratch orgs (xz and tallowdate shapes), each loaded with b_two_keepers.

    Teardown drops every graph that holds one of these ids.
    """
    client = FalkorClient()
    ids = {"xz": new_org_id(), "tallowdate": new_org_id()}
    try:
        for org in ids.values():
            graph = f"org_{org}"
            assert owned(graph), graph
            client.drop(graph)
            FIXTURE.build(client, graph)
        yield ids
    finally:
        for org in ids.values():
            drop_owned(client, org)


@pytest.fixture
def real_graphs_untouched():
    """Fails the test if it changed org_xz or org_tallowdate. Reads and writes both count."""
    client = FalkorClient()
    before = {g: fingerprint(client, g) for g in REAL_GRAPHS}
    yield
    after = {g: fingerprint(client, g) for g in REAL_GRAPHS}
    changed = changed_real_graphs(before, after)
    assert not changed, f"a test wrote to a real graph: {changed}"


@pytest.fixture(scope="module")
def client() -> FalkorClient:
    return FalkorClient()


@pytest.fixture
def org_graph(client):
    org = "bd" + uuid.uuid4().hex[:10]
    g = f"org_{org}"
    client.drop(g)
    client.query(g, "MERGE (:Org {id: $id, name: $id, pack: 'oss'})", {"id": org})
    yield org
    client.drop(g)
