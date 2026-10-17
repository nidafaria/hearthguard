"""SHARES edges builder (docs/HEARTHGUARD.md §6.1, §7.1).

Builds (:Actor)-[:SHARES {signal: ...}]->(:Actor) edges between actors who share observable signals:
  - 'creation_window': first_seen_in_org within 7 days
  - 'only_interacts_with_target': actors who vouch for the same candidate target
  - 'same_thread_burst': claims asserted within 48 hours of each other
  - 'domain_hash': identical domain_hash property (when present)

All edges are idempotent MERGE operations.
"""

from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient

WRITE_TIMEOUT_MS = 60_000

CREATION_WINDOW_CYPHER = """
MATCH (a:Actor), (b:Actor)
WHERE a.hid < b.hid
  AND a.first_seen_in_org IS NOT NULL
  AND b.first_seen_in_org IS NOT NULL
  AND abs(a.first_seen_in_org - b.first_seen_in_org) <= 7 * 86400
  AND ($T IS NULL OR (a.first_seen_in_org <= $T AND b.first_seen_in_org <= $T))
MERGE (a)-[:SHARES {signal: 'creation_window'}]->(b)
MERGE (b)-[:SHARES {signal: 'creation_window'}]->(a)
"""

SAME_TARGET_CYPHER = """
MATCH (a:Actor)-[:ASSERTED]->(ca:Claim {kind: 'VOUCH'}),
      (b:Actor)-[:ASSERTED]->(cb:Claim {kind: 'VOUCH'})
WHERE a.hid < b.hid
  AND ca.target_hid IS NOT NULL
  AND ca.target_hid = cb.target_hid
  AND ($T IS NULL OR (ca.at <= $T AND cb.at <= $T))
MERGE (a)-[:SHARES {signal: 'only_interacts_with_target'}]->(b)
MERGE (b)-[:SHARES {signal: 'only_interacts_with_target'}]->(a)
"""

BURST_CYPHER = """
MATCH (a:Actor)-[:ASSERTED]->(ca:Claim),
      (b:Actor)-[:ASSERTED]->(cb:Claim)
WHERE a.hid < b.hid
  AND abs(ca.at - cb.at) <= 48 * 3600
  AND ($T IS NULL OR (ca.at <= $T AND cb.at <= $T))
MERGE (a)-[:SHARES {signal: 'same_thread_burst'}]->(b)
MERGE (b)-[:SHARES {signal: 'same_thread_burst'}]->(a)
"""

DOMAIN_CYPHER = """
MATCH (a:Actor), (b:Actor)
WHERE a.hid < b.hid
  AND a.domain_hash IS NOT NULL
  AND a.domain_hash = b.domain_hash
MERGE (a)-[:SHARES {signal: 'domain_hash'}]->(b)
MERGE (b)-[:SHARES {signal: 'domain_hash'}]->(a)
"""


def build_shares_edges(
    client: FalkorClient,
    graph: str,
    T: int | None = None,
    timeout_ms: int = WRITE_TIMEOUT_MS,
) -> dict[str, int]:
    """Build SHARES edges for all observable signals up to time T (or all time if T is None).

    Returns a dict mapping each signal to the count of edges created or existing.
    """
    params = {"T": T}
    counts: dict[str, int] = {}
    queries = [
        ("creation_window", CREATION_WINDOW_CYPHER),
        ("only_interacts_with_target", SAME_TARGET_CYPHER),
        ("same_thread_burst", BURST_CYPHER),
        ("domain_hash", DOMAIN_CYPHER),
    ]

    for signal, cypher in queries:
        client.query(graph, cypher, params, timeout_ms=timeout_ms)
        r = client.query(
            graph,
            "MATCH ()-[s:SHARES {signal: $sig}]->() RETURN count(s)",
            {"sig": signal},
            timeout_ms=timeout_ms,
        )
        counts[signal] = r.result_set[0][0] if r.result_set else 0

    total_r = client.query(
        graph,
        "MATCH ()-[s:SHARES]->() RETURN count(s)",
        timeout_ms=timeout_ms,
    )
    counts["total"] = total_r.result_set[0][0] if total_r.result_set else 0
    return counts


def create_shares_edge(
    client: FalkorClient,
    graph: str,
    a_hid: str,
    b_hid: str,
    signal: str,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> None:
    """Explicitly create bidirectional SHARES edges between two actors."""
    client.query(
        graph,
        "MATCH (a:Actor {hid: $a}), (b:Actor {hid: $b}) "
        "MERGE (a)-[:SHARES {signal: $s}]->(b) "
        "MERGE (b)-[:SHARES {signal: $s}]->(a)",
        {"a": a_hid, "b": b_hid, "s": signal},
        timeout_ms=timeout_ms,
    )
