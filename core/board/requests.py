"""Objections and requests between agents (docs/HEARTHGUARD.md 8.2).

The Skeptic's objection becomes a Request the Investigator must answer before the finding returns
to the board. All state is in the graph:

  (:Request {id, from, to, question, status})-[:FOR]->(:Objection {id, by, reason, open})
      -[:ON]->(:Finding)

A finding with an open objection has status 'held'. Answering the last open request closes the
objection, and once no objection is open the finding goes back to 'open'. A finding that was
dismissed or sent is never reopened by this module. No LLM.
"""

from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient


def raise_objection(
    client: FalkorClient,
    graph: str,
    finding_id: str,
    objection_id: str,
    reason: str,
    request_id: str,
    frm: str,
    to: str,
    question: str,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> bool:
    """MERGE the objection and its request, and hold the finding. False if the finding is absent."""
    r = client.query(
        graph,
        "MATCH (f:Finding {id: $fid}) "
        "MERGE (o:Objection {id: $oid}) "
        "ON CREATE SET o.by = 'skeptic', o.reason = $reason, o.open = true "
        "MERGE (o)-[:ON]->(f) "
        "MERGE (r:Request {id: $rid}) "
        "ON CREATE SET r.from = $frm, r.to = $to, r.question = $question, r.status = 'OPEN' "
        "MERGE (r)-[:FOR]->(o) "
        "WITH f, o WHERE f.status = 'open' OR f.status = 'held' "
        "SET f.status = 'held' RETURN f.id",
        {
            "fid": finding_id,
            "oid": objection_id,
            "reason": reason,
            "rid": request_id,
            "frm": frm,
            "to": to,
            "question": question,
        },
        timeout_ms=timeout_ms,
    )
    return bool(r.result_set)


def open_requests(
    client: FalkorClient, graph: str, finding_id: str, timeout_ms: int = DEFAULT_TIMEOUT_MS
) -> list[dict]:
    r = client.query(
        graph,
        "MATCH (r:Request {status: 'OPEN'})-[:FOR]->(:Objection)-[:ON]->(:Finding {id: $fid}) "
        "RETURN r.id, r.to, r.question ORDER BY r.id",
        {"fid": finding_id},
        timeout_ms=timeout_ms,
    )
    return [{"id": i, "to": t, "question": q} for i, t, q in r.result_set]


def answer_request(
    client: FalkorClient,
    graph: str,
    request_id: str,
    answer: str,
    now: int,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> bool:
    """Answer a request. True if this answer released the finding back to the board."""
    r = client.query(
        graph,
        "MATCH (r:Request {id: $rid, status: 'OPEN'})-[:FOR]->(o:Objection)-[:ON]->(f:Finding) "
        "SET r.status = 'ANSWERED', r.answer = $answer, r.answered_at = $now "
        "RETURN o.id, f.id",
        {"rid": request_id, "answer": answer, "now": now},
        timeout_ms=timeout_ms,
    )
    if not r.result_set:
        return False
    oid, fid = r.result_set[0]
    client.query(
        graph,
        "MATCH (o:Objection {id: $oid}) "
        "OPTIONAL MATCH (r:Request {status: 'OPEN'})-[:FOR]->(o) "
        "WITH o, count(r) AS still SET o.open = (still > 0)",
        {"oid": oid},
        timeout_ms=timeout_ms,
    )
    return release_if_clear(client, graph, fid, timeout_ms)


def release_if_clear(
    client: FalkorClient, graph: str, finding_id: str, timeout_ms: int = DEFAULT_TIMEOUT_MS
) -> bool:
    """Set a held finding back to 'open' if no objection on it is still open."""
    r = client.query(
        graph,
        "MATCH (f:Finding {id: $fid, status: 'held'}) "
        "OPTIONAL MATCH (o:Objection {open: true})-[:ON]->(f) "
        "WITH f, count(o) AS n WHERE n = 0 "
        "SET f.status = 'open' RETURN f.id",
        {"fid": finding_id},
        timeout_ms=timeout_ms,
    )
    return bool(r.result_set)
