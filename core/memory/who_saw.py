"""Who-saw-what memory (docs/HEARTHGUARD.md §9, §6.1): PARTICIPATES_IN and WATCHES {since}.

Writes the visibility edges an org graph needs, and answers one question the Liaison asks before it
sends anything: has the owner already acknowledged this finding? A finding the owner acknowledged is
never re-sent (spec §9, "so the Liaison never re-sends what the owner already acknowledged").

Edges written (all MERGE, so a second write changes no count):
  (:Actor)-[:PARTICIPATES_IN {since, last_at}]->(:Place)
  (:Role)-[:WATCHES {since}]->(:Place)

The acknowledgement check reads (:OwnerDecision)-[:ABOUT]->(:Finding) nodes. An OwnerDecision is
only ever written by the owner's own action; this module never creates one.
"""

from core.graph.client import FalkorClient

WRITE_TIMEOUT_MS = 30_000
READ_TIMEOUT_MS = 10_000

PARTICIPATES_CYPHER = (
    "UNWIND $rows AS r "
    "MERGE (a:Actor {hid: r.hid}) "
    "MERGE (p:Place {ref: r.place}) "
    "MERGE (a)-[e:PARTICIPATES_IN]->(p) "
    "SET e.since = CASE WHEN e.since IS NULL OR r.since < e.since THEN r.since ELSE e.since END, "
    "    e.last_at = CASE WHEN e.last_at IS NULL OR r.last_at > e.last_at THEN r.last_at "
    "                     ELSE e.last_at END"
)
WATCHES_CYPHER = (
    "UNWIND $rows AS r "
    "MERGE (ro:Role {name: r.role}) "
    "MERGE (p:Place {ref: r.place}) "
    "MERGE (ro)-[w:WATCHES]->(p) "
    "SET w.since = CASE WHEN w.since IS NULL OR r.since < w.since THEN r.since ELSE w.since END"
)
PLACE_CYPHER = "UNWIND $rows AS r MERGE (p:Place {ref: r.ref}) SET p.kind = r.kind"
RECORDED_IN_CYPHER = (
    "UNWIND $rows AS r "
    "MATCH (x:Action {ref: r.ref}) "
    "MATCH (p:Place {ref: r.place}) "
    "MERGE (x)-[:RECORDED_IN]->(p)"
)
ACK_CYPHER = (
    "MATCH (d:OwnerDecision)-[:ABOUT]->(f:Finding {id: $id}) "
    "WHERE d.at <= $now "
    "RETURN d.at AS at, d.text AS text ORDER BY at LIMIT 10"
)


def write_participation(client: FalkorClient, graph: str, rows: list[dict]) -> None:
    """rows: {hid, place, since, last_at}. Idempotent: the earliest since and latest last_at win."""
    if rows:
        client.query(graph, PARTICIPATES_CYPHER, {"rows": rows}, timeout_ms=WRITE_TIMEOUT_MS)


def write_watches(client: FalkorClient, graph: str, rows: list[dict]) -> None:
    """rows: {role, place, since}. Idempotent: the earliest since wins."""
    if rows:
        client.query(graph, WATCHES_CYPHER, {"rows": rows}, timeout_ms=WRITE_TIMEOUT_MS)


def participation_rows(events: list[dict]) -> list[dict]:
    """Fold events {hid, place, at} into one PARTICIPATES_IN row per (actor, place).

    since is the earliest event time and last_at the latest. Domain-free: a pack's parser decides
    which records count as events and which place each one happened in.
    """
    folded: dict[tuple[str, str], list[int]] = {}
    for e in events:
        key = (e["hid"], e["place"])
        lo_hi = folded.setdefault(key, [e["at"], e["at"]])
        lo_hi[0], lo_hi[1] = min(lo_hi[0], e["at"]), max(lo_hi[1], e["at"])
    return [
        {"hid": hid, "place": place, "since": lo, "last_at": hi}
        for (hid, place), (lo, hi) in sorted(folded.items())
    ]


def write_places(client: FalkorClient, graph: str, rows: list[dict]) -> None:
    """rows: {ref, kind}. Idempotent (MERGE on Place.ref)."""
    if rows:
        client.query(graph, PLACE_CYPHER, {"rows": rows}, timeout_ms=WRITE_TIMEOUT_MS)


def write_recorded_in(client: FalkorClient, graph: str, rows: list[dict]) -> None:
    """rows: {ref, place}: Action `ref` was recorded in Place `place`. Both must already exist."""
    if rows:
        client.query(graph, RECORDED_IN_CYPHER, {"rows": rows}, timeout_ms=WRITE_TIMEOUT_MS)


def already_acknowledged(client: FalkorClient, graph: str, finding_id: str, now: int) -> bool:
    """True if the owner has an OwnerDecision about this finding at or before `now`.

    The Liaison calls this before it sends anything. A finding with no owner decision is not
    acknowledged, so the answer is False and the send may go ahead as usual.
    """
    r = client.query(graph, ACK_CYPHER, {"id": finding_id, "now": now}, timeout_ms=READ_TIMEOUT_MS)
    return len(r.result_set) > 0
