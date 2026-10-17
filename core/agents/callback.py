"""Mark callback done (spec 12.2, finance): the owner says they called back on the number on file.

The tap writes the verification on the Path of the bank change. It is the only write, it happens
once per action (a double tap changes nothing), and it contacts no one. The Bypass detector is
not touched: it reads `Path.callback` as before, so the callback property resolves from the
record. Channel and approvers are not changed by a callback and stay as recorded.
"""

from core.graph.client import FalkorClient

WRITE_MS = 10_000


def mark_callback_done(client: FalkorClient, graph: str, action_ref: str, now: int) -> bool:
    """Record the callback on the Path of one bank change. True only for the first tap."""
    r = client.query(
        graph,
        "MATCH (a:Action {ref: $ref, kind: 'bank_change'})-[:VIA]->(p:Path) "
        "WHERE coalesce(p.verified, false) = false "
        "SET p.verified = true, p.callback = true, p.callback_marked_at = $now "
        "RETURN p.callback_marked_at",
        {"ref": action_ref, "now": now},
        timeout_ms=WRITE_MS,
    )
    return bool(r.result_set)
