"""Block D test helper: one Cypher call on a throw-away org graph (real FalkorDB, no mocks)."""

from core.graph.client import FalkorClient


def q(client: FalkorClient, org: str, cypher: str, params: dict | None = None):
    return client.query(f"org_{org}", cypher, params, timeout_ms=30_000)
