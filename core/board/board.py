"""The task board (docs/HEARTHGUARD.md 8.2), kept in the org graph as (:Task) nodes.

Owner: Block F. No LLM here; the board is plain Cypher.

  - add_task      MERGE on Task.id, so adding the same task twice leaves one task.
  - claim         the 8.2 query: highest priority first, then oldest, then id (so a tie is never
                  broken by chance). A claim is a 30 s lease. An expired lease reopens the task.
  - complete      accepted only from the agent that holds the claim, and only if the org graph's
                  input_version is the one the task recorded at claim time. If the graph changed
                  while the agent worked, the result is rejected and the task goes back to OPEN.
  - hold          a task that guardrails could not finish waits, bounded, then goes to human review.
  - send_note     one Note per unique key. The second call, even a racing one, sends nothing.

FalkorDB runs one write query at a time per graph, so each of these is one query and is atomic.
Every query takes an explicit timeout.
"""

from redis.exceptions import ResponseError

from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient, require_timeout

LEASE_MS = 30_000  # 8.2

OPEN, CLAIMED, DONE, HELD, HUMAN_REVIEW = "OPEN", "CLAIMED", "DONE", "HELD", "HUMAN_REVIEW"

# complete() outcomes
ACCEPTED = "ACCEPTED"
STALE_REQUEUED = "STALE_REQUEUED"
NOT_OWNER = "NOT_OWNER"
NO_TASK = "NO_TASK"

CLAIM_QUERY = (
    "MATCH (t:Task) "
    "WHERE t.status = 'OPEN' OR (t.status = 'CLAIMED' AND t.lease_until < $now) "
    "WITH t ORDER BY t.priority DESC, t.created_at ASC, t.id ASC LIMIT 1 "
    "OPTIONAL MATCH (o:Org {id: $org}) "
    "SET t.status = 'CLAIMED', t.claimed_by = $agent, t.lease_until = $now + $lease, "
    "t.input_version = coalesce(o.input_version, 0), t.attempts = coalesce(t.attempts, 0) + 1 "
    "RETURN t.id"
)


BOARD_PREFIXES = ("org_", "redteam_", "harden_", "census_")  # 8.2: one board for all of them


def org_of(graph: str) -> str:
    """The id the graph's (:Org) node carries: the graph name without its prefix."""
    for p in BOARD_PREFIXES:
        if graph.startswith(p):
            return graph[len(p) :]
    raise ValueError(f"the board lives in an org, red-team, harden or census graph, not {graph!r}")


def add_task(
    client: FalkorClient,
    graph: str,
    task_id: str,
    kind: str,
    priority: int,
    created_at: int,
    *,
    synthetic: bool = False,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> bool:
    """MERGE the task on its id. True if it was new."""
    r = client.query(
        graph,
        "MERGE (t:Task {id: $id}) "
        "ON CREATE SET t.kind = $kind, t.status = 'OPEN', t.priority = $priority, "
        "t.created_at = $created_at, t.synthetic = $synthetic",
        {
            "id": task_id,
            "kind": kind,
            "priority": priority,
            "created_at": created_at,
            "synthetic": synthetic,
        },
        timeout_ms=timeout_ms,
    )
    return r.nodes_created > 0


def bump_version(client: FalkorClient, graph: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> int:
    """Call after any write that a result could depend on. Returns the new input_version."""
    r = client.query(
        graph,
        "MERGE (o:Org {id: $org}) SET o.input_version = coalesce(o.input_version, 0) + 1 "
        "RETURN o.input_version",
        {"org": org_of(graph)},
        timeout_ms=timeout_ms,
    )
    return r.result_set[0][0]


def input_version(client: FalkorClient, graph: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> int:
    r = client.query(
        graph,
        "OPTIONAL MATCH (o:Org {id: $org}) RETURN coalesce(o.input_version, 0)",
        {"org": org_of(graph)},
        timeout_ms=timeout_ms,
    )
    return r.result_set[0][0]


def claim(
    client: FalkorClient,
    graph: str,
    agent: str,
    now: int,
    *,
    lease_ms: int = LEASE_MS,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> str | None:
    """Claim the next task for `agent` for lease_ms. None if nothing is claimable."""
    r = client.query(
        graph,
        CLAIM_QUERY,
        {"now": now, "agent": agent, "lease": lease_ms, "org": org_of(graph)},
        timeout_ms=timeout_ms,
    )
    return r.result_set[0][0] if r.result_set else None


def renew(
    client: FalkorClient,
    graph: str,
    task_id: str,
    agent: str,
    now: int,
    *,
    lease_ms: int = LEASE_MS,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> bool:
    """Extend a lease. Refused unless `agent` still holds the claim."""
    r = client.query(
        graph,
        "MATCH (t:Task {id: $id, status: 'CLAIMED', claimed_by: $agent}) "
        "SET t.lease_until = $now + $lease RETURN t.id",
        {"id": task_id, "agent": agent, "now": now, "lease": lease_ms},
        timeout_ms=timeout_ms,
    )
    return bool(r.result_set)


def complete(
    client: FalkorClient,
    graph: str,
    task_id: str,
    agent: str,
    now: int,
    result_ref: str | None = None,
    *,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> str:
    """Hand in a result. ACCEPTED, STALE_REQUEUED (graph changed; task is OPEN again), NOT_OWNER
    (someone else holds or finished it) or NO_TASK."""
    p = {"id": task_id, "agent": agent, "now": now, "ref": result_ref, "org": org_of(graph)}
    ok = client.query(
        graph,
        "MATCH (t:Task {id: $id, status: 'CLAIMED', claimed_by: $agent}) "
        "OPTIONAL MATCH (o:Org {id: $org}) "
        "WITH t, o WHERE t.input_version = coalesce(o.input_version, 0) "
        "SET t.status = 'DONE', t.result_ref = $ref, t.done_at = $now RETURN t.id",
        p,
        timeout_ms=timeout_ms,
    )
    if ok.result_set:
        return ACCEPTED
    # Not accepted. A stale result is requeued, but only by the agent that holds the claim.
    requeued = client.query(
        graph,
        "MATCH (t:Task {id: $id, status: 'CLAIMED', claimed_by: $agent}) "
        "REMOVE t.claimed_by, t.lease_until "
        "SET t.status = 'OPEN', t.requeues = coalesce(t.requeues, 0) + 1 RETURN t.id",
        p,
        timeout_ms=timeout_ms,
    )
    if requeued.result_set:
        return STALE_REQUEUED
    exists = client.query(
        graph, "MATCH (t:Task {id: $id}) RETURN t.id", p, timeout_ms=timeout_ms
    ).result_set
    return NOT_OWNER if exists else NO_TASK


def hold(
    client: FalkorClient,
    graph: str,
    task_id: str,
    reason: str,
    failure_type: str,
    until: int,
    *,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> bool:
    """Park a task. A HELD task is never claimed. It has a deadline: see expire_holds."""
    r = client.query(
        graph,
        "MATCH (t:Task {id: $id}) WHERE t.status <> 'DONE' "
        "REMOVE t.claimed_by, t.lease_until "
        "SET t.status = 'HELD', t.hold_reason = $reason, t.failure_type = $ft, "
        "t.hold_until = $until RETURN t.id",
        {"id": task_id, "reason": reason, "ft": failure_type, "until": until},
        timeout_ms=timeout_ms,
    )
    return bool(r.result_set)


def expire_holds(
    client: FalkorClient, graph: str, now: int, timeout_ms: int = DEFAULT_TIMEOUT_MS
) -> int:
    """A hold that reached its deadline goes to a person. Returns how many."""
    r = client.query(
        graph,
        "MATCH (t:Task {status: 'HELD'}) WHERE t.hold_until <= $now "
        "SET t.status = 'HUMAN_REVIEW' RETURN count(t)",
        {"now": now},
        timeout_ms=timeout_ms,
    )
    return r.result_set[0][0]


def get_task(
    client: FalkorClient, graph: str, task_id: str, timeout_ms: int = DEFAULT_TIMEOUT_MS
) -> dict | None:
    r = client.query(
        graph, "MATCH (t:Task {id: $id}) RETURN t", {"id": task_id}, timeout_ms=timeout_ms
    )
    return dict(r.result_set[0][0].properties) if r.result_set else None


def tasks_by_status(
    client: FalkorClient, graph: str, timeout_ms: int = DEFAULT_TIMEOUT_MS
) -> dict[str, int]:
    r = client.query(graph, "MATCH (t:Task) RETURN t.status, count(t)", timeout_ms=timeout_ms)
    return {s: n for s, n in r.result_set}


def note_key(finding_id: str, routed_to_hid: str) -> str:
    """The unique action key of a note: one note per finding and person."""
    return f"note:{finding_id}:{routed_to_hid}"


def send_note(
    client: FalkorClient,
    graph: str,
    finding_id: str,
    routed_to_hid: str,
    now: int,
    *,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> bool:
    """True only for the call that created the note. Every other call, however it races, is False.

    MERGE on the unique Note.id (5.6 constraint). Two writers racing past the MERGE hit the
    constraint; the loser gets an error, which means "already sent".
    """
    key = note_key(finding_id, routed_to_hid)
    try:
        r = client.query(
            graph,
            "MERGE (n:Note {id: $id}) ON CREATE SET n.sent_at = $now, n.routed_to_hid = $hid",
            {"id": key, "now": now, "hid": routed_to_hid},
            timeout_ms=require_timeout(timeout_ms),
        )
    except ResponseError as e:
        if "unique" in str(e).lower() or "constraint" in str(e).lower():
            return False
        raise
    if r.nodes_created == 0:
        return False
    client.query(
        graph,
        "MATCH (n:Note {id: $id}), (f:Finding {id: $fid}) MERGE (n)-[:FOR]->(f)",
        {"id": key, "fid": finding_id},
        timeout_ms=timeout_ms,
    )
    return True
