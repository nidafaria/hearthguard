"""Fixtures shared by the integration tests."""

import pytest

from core.graph.client import FalkorClient
from packs.oss import git_ingest, xz_graph


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


# The local GitHub stub for the connect tests (the same `site` fixture the unit tests use).
from tests.unit.conftest import site  # noqa: E402,F401
