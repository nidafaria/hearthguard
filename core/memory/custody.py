"""Custody memory (docs/HEARTHGUARD.md §9, §4.4): Day 1 write, Day 4 recall across sessions.

The project's Action Boundary (§4.4) forbids automatic blocking of releases or payments.
So Hearthguard WARNS and RECALLS, but never automatically blocks.

Nodes and relationships written:
  (:Actor {hid, name})
  (:Privilege {kind})
  (:CustodyRecord {id, at, custodian_hid, privilege, status})
  (Actor)-[:GRANTED {at, privilege}]->(Privilege)
  (Actor)-[:HOLDS_CUSTODY {since}]->(CustodyRecord)

Every write is MERGE on unique keys (idempotent, §6.6).
Reads are parameterized and time-bounded with explicit timeouts.
"""

from dataclasses import dataclass
from typing import Any

from core.graph.client import FalkorClient
from core.policy import boundary

READ_TIMEOUT_MS = 10_000
WRITE_TIMEOUT_MS = 30_000

WRITE_CUSTODY_CYPHER = (
    "MERGE (a:Actor {hid: $custodian_hid}) "
    "SET a.name = $custodian_name "
    "MERGE (p:Privilege {kind: $privilege}) "
    "MERGE (a)-[g:GRANTED {privilege: $privilege}]->(p) "
    "SET g.at = CASE WHEN g.at IS NULL OR $at < g.at THEN $at ELSE g.at END "
    "MERGE (c:CustodyRecord {id: $record_id}) "
    "SET c.at = $at, c.custodian_hid = $custodian_hid, c.privilege = $privilege, "
    "    c.status = 'active' "
    "MERGE (a)-[h:HOLDS_CUSTODY]->(c) "
    "SET h.since = CASE WHEN h.since IS NULL OR $at < h.since THEN $at ELSE h.since END"
)

RECALL_CUSTODY_CYPHER = (
    "MATCH (a:Actor)-[g:GRANTED]->(p:Privilege {kind: $privilege}) "
    "WHERE g.at <= $as_of_t "
    "RETURN a.hid AS hid, a.name AS name, g.at AS at "
    "ORDER BY g.at ASC"
)

CHECK_ACTOR_CUSTODY_CYPHER = (
    "MATCH (a:Actor {hid: $actor_hid})-[g:GRANTED]->(p:Privilege {kind: $privilege}) "
    "WHERE g.at <= $as_of_t "
    "RETURN a.hid AS hid, a.name AS name, g.at AS at"
)


@dataclass(frozen=True)
class CustodyEvaluation:
    """Outcome of evaluating an action against recalled custody memory and the Action Boundary."""

    actor_hid: str
    actor_name: str
    action_kind: str
    at: int
    has_custody: bool
    recalled_custodians: list[dict[str, Any]]
    blocked: bool
    boundary_refusal: str | None
    warning_note: str | None
    suggested_step: str | None
    boundary_level: int


def custody_record_id(graph: str, privilege: str, custodian_hid: str) -> str:
    """Deterministic unique id for a custody record."""
    return f"custody:{graph}:{privilege}:{custodian_hid}"


def record_custody_baseline(
    client: FalkorClient,
    graph: str,
    custodian_hid: str,
    custodian_name: str,
    privilege: str = "release",
    at: int = 1_700_000_000,
) -> str:
    """Record initial custody baseline on Day 1.

    Idempotent: MERGE on Actor.hid, Privilege.kind, and CustodyRecord.id.
    """
    rec_id = custody_record_id(graph, privilege, custodian_hid)
    params = {
        "custodian_hid": custodian_hid,
        "custodian_name": custodian_name,
        "privilege": privilege,
        "record_id": rec_id,
        "at": at,
    }
    client.query(graph, WRITE_CUSTODY_CYPHER, params, timeout_ms=WRITE_TIMEOUT_MS)
    return rec_id


def recall_custody_baseline(
    client: FalkorClient,
    graph: str,
    privilege: str = "release",
    as_of_t: int = 2_000_000_000,
) -> list[dict[str, Any]]:
    """Recall who held custody as of timestamp `as_of_t` from the graph."""
    params = {"privilege": privilege, "as_of_t": as_of_t}
    res = client.query(graph, RECALL_CUSTODY_CYPHER, params, timeout_ms=READ_TIMEOUT_MS)
    custodians = []
    for row in res.result_set:
        custodians.append({"hid": row[0], "name": row[1] or row[0], "granted_at": row[2]})
    return custodians


def has_custody(
    client: FalkorClient,
    graph: str,
    actor_hid: str,
    privilege: str = "release",
    as_of_t: int = 2_000_000_000,
) -> bool:
    """Check if a specific actor has established custody for `privilege` as of `as_of_t`."""
    params = {"actor_hid": actor_hid, "privilege": privilege, "as_of_t": as_of_t}
    res = client.query(graph, CHECK_ACTOR_CUSTODY_CYPHER, params, timeout_ms=READ_TIMEOUT_MS)
    return len(res.result_set) > 0


def evaluate_custody_action(
    client: FalkorClient,
    graph: str,
    actor_hid: str,
    actor_name: str,
    action_kind: str = "release",
    at: int = 1_700_259_200,
    simulate_blocking_attempt: bool = True,
) -> CustodyEvaluation:
    """Evaluate an action against recalled custody memory and enforce the Action Boundary (§4.4).

    Crucial: §4.4 Never: 'block a release or payment'.
    Automatic blocking is strictly forbidden and refused by boundary.check().
    Instead, Hearthguard RECALLS custody baseline from graph memory and WARNS with a private note.
    """
    actor_ok = has_custody(client, graph, actor_hid, privilege=action_kind, as_of_t=at)
    recalled = recall_custody_baseline(client, graph, privilege=action_kind, as_of_t=at)

    blocked = False
    refusal_reason: str | None = None

    if simulate_blocking_attempt:
        # Demonstrate Action Boundary §4.4: attempting automatic blocking is refused
        try:
            boundary.check("block_release_or_payment", recipient="owner")
            blocked = True
        except boundary.BoundaryViolation as e:
            refusal_reason = str(e)

    if actor_ok:
        return CustodyEvaluation(
            actor_hid=actor_hid,
            actor_name=actor_name,
            action_kind=action_kind,
            at=at,
            has_custody=True,
            recalled_custodians=recalled,
            blocked=blocked,
            boundary_refusal=refusal_reason,
            warning_note=None,
            suggested_step=None,
            boundary_level=int(boundary.Level.ANALYSE),
        )

    # Actor has NO custody: Hearthguard WARNS and RECALLS, does NOT block
    custodian_names = ", ".join(c["name"] for c in recalled) or "no prior custodian"

    # Action Boundary Level 1: private note to the person in charge, phrased as a question
    boundary.check("send_private_note", recipient="owner")
    warning_note = (
        f"On Day 1, {custodian_names} was verified as custodian with {action_kind} rights. "
        f"On Day 4, unvouched account '{actor_name}' attempted a {action_kind} without prior grant "
        f"or custody handoff. Should this release proceed, or would you like to verify the "
        f"custodian?"
    )

    # Action Boundary Level 2: suggest a concrete safety step with measured effect
    boundary.check("suggest_safety_step", recipient="owner")
    suggested_step = (
        f"Suggested safety step: Verify {action_kind} authorization out-of-band with recorded "
        f"custodian ({custodian_names}) before signing or publishing."
    )

    return CustodyEvaluation(
        actor_hid=actor_hid,
        actor_name=actor_name,
        action_kind=action_kind,
        at=at,
        has_custody=False,
        recalled_custodians=recalled,
        blocked=blocked,
        boundary_refusal=refusal_reason,
        warning_note=warning_note,
        suggested_step=suggested_step,
        boundary_level=int(boundary.Level.PRIVATE_NOTE),
    )
