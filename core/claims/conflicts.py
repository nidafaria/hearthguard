"""Conflict links between claims (docs/HEARTHGUARD.md §6.1, §7.2).

Writes CONTRADICTS, SUPERSEDES and QUALIFIES.

core.policy.conflict.resolve() decides each pair, unchanged. This module only:
  - reads each claim's time from the graph,
  - takes each claim's authority class from the caller (the policy never classifies actors),
  - writes the links that resolve() returns. Claims are kept as written: no node is deleted.

What is NOT here: finding which claim pairs contradict. No detector does that yet, so the caller
supplies the pairs. Until one does, the graph only holds the links for pairs someone gave.
Writes are MERGE on the two claim ids and the relation, so writing a pair twice makes one edge.
"""

from core.graph.client import FalkorClient
from core.policy import conflict as cf

WRITE_TIMEOUT_MS = 30_000
READ_TIMEOUT_MS = 10_000

_RELATION = {"CONTRADICTS": "CONTRADICTS", "SUPERSEDES": "SUPERSEDES", "QUALIFIES": "QUALIFIES"}


def _claim_times(client: FalkorClient, graph: str, ids: list[str]) -> dict[str, int | None]:
    r = client.query(
        graph,
        "MATCH (c:Claim) WHERE c.id IN $ids RETURN c.id AS id, c.at AS at",
        {"ids": ids},
        timeout_ms=READ_TIMEOUT_MS,
    )
    found = {row[0]: row[1] for row in r.result_set}
    missing = [i for i in ids if i not in found]
    if missing:
        raise ValueError(f"claim not in graph: {missing}")
    return found


def link_pair(
    client: FalkorClient,
    graph: str,
    a: dict,
    b: dict,
) -> cf.Resolution:
    """a, b: {id, source, exception_to?}. Decide the pair with resolve(), then write its links."""
    times = _claim_times(client, graph, [a["id"], b["id"]])
    res = cf.resolve(
        [
            cf.Claim(a["id"], a["source"], times[a["id"]], a.get("exception_to")),
            cf.Claim(b["id"], b["source"], times[b["id"]], b.get("exception_to")),
        ]
    )
    for frm, rel, to in res.links:
        if rel not in _RELATION:
            raise ValueError(f"unknown relation {rel!r}")
        client.query(
            graph,
            "MATCH (x:Claim {id: $from}), (y:Claim {id: $to}) "
            f"MERGE (x)-[r:{rel}]->(y) SET r.status = $status, r.basis = $basis",
            {"from": frm, "to": to, "status": res.status, "basis": res.basis},
            timeout_ms=WRITE_TIMEOUT_MS,
        )
    return res
