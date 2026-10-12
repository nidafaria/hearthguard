"""Scratch graphs for the inbox integration tests, and a guard that the real graphs stay untouched.

Every test gets its own org ids: "tst" plus 10 hex characters. Graph names carry that id
(org_tst<hex>, harden_xz_..._tst<hex>..., org_hza...), so a graph is ours only if its name holds
the id. Teardown drops only graphs whose names hold this test's ids. Nothing else is cleared or
written. org_xz and org_tallowdate are never written here: the guard fixture fails the test if
their fingerprint changes.
"""

import re
import uuid

from core.graph.client import FalkorClient
from tests.fixtures.takeover_cases import CASES as TAKEOVER_CASES

REAL_GRAPHS = ("org_xz", "org_tallowdate")
_OWNED = re.compile(r"tst[0-9a-f]{10}")
FIXTURE = next(c for c in TAKEOVER_CASES if c.name == "b_two_keepers")


def new_org_id() -> str:
    return f"tst{uuid.uuid4().hex[:10]}"


def owned(graph: str) -> bool:
    """True only for a graph name that holds a test id made by new_org_id()."""
    return graph not in REAL_GRAPHS and _OWNED.search(graph) is not None


def _names(client: FalkorClient) -> list[str]:
    return [
        g if isinstance(g, str) else g.decode() for g in client.db.execute_command("GRAPH.LIST")
    ]


def drop_owned(client: FalkorClient, org_id: str) -> None:
    """Drop every graph whose name holds this test's org id, and nothing else."""
    for name in _names(client):
        if org_id in name and owned(name):
            client.drop(name)


def fingerprint(client: FalkorClient, graph: str):
    """Node and edge counts by label and type. None if the graph does not exist."""
    if graph not in _names(client):
        return None
    nodes = client.query(graph, "MATCH (n) RETURN labels(n)[0], count(n)", timeout_ms=60_000)
    edges = client.query(graph, "MATCH ()-[r]->() RETURN type(r), count(r)", timeout_ms=60_000)
    return (
        tuple(sorted((str(k), v) for k, v in nodes.result_set)),
        tuple(sorted((str(k), v) for k, v in edges.result_set)),
    )


def changed_real_graphs(before: dict, after: dict) -> list[str]:
    """The real graphs whose fingerprint differs between two snapshots. Pure, unit-tested."""
    return [g for g in REAL_GRAPHS if before.get(g) != after.get(g)]
