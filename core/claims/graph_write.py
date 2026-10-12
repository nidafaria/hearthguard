"""Write the Reader's accepted claims into an org graph (docs/HEARTHGUARD.md §6.1, text part).

    (:Source {type, ref})-[:HAS]->(:Span {text, offset, at})
    (:Claim {id, kind, confidence, modality, at})-[:FROM]->(:Span)
    (:Actor)-[:ASSERTED]->(:Claim)

MERGE on unique keys only, so running it twice changes nothing. Claim.id is
"<message id>:<kind>:<offset>". An Actor that already exists (for example a git author with the
same hashed email) is left exactly as it is. An Actor that does not exist yet is created with
`source = 'mail'` and `first_seen_in_org` = the time of the first claim written for them, so
history from the mailing list is never presented as older than what we saw.
The span text is the quote (at most 25 words of the cleaned message), never a whole message.
"""

from collections.abc import Iterator
from datetime import datetime
from typing import Any

from core.graph.client import FalkorClient
from core.graph.schema import apply_schema

BATCH = 300
WRITE_TIMEOUT_MS = 60_000


def to_epoch(date_utc: str) -> int:
    return int(datetime.fromisoformat(date_utc.replace("Z", "+00:00")).timestamp())


def rows_from_entries(entries: list[dict]) -> tuple[list[dict], dict]:
    """Flat claim rows for the graph, and counts of what was left out (and why)."""
    rows: list[dict] = []
    left_out = {"no_date": 0, "no_author": 0}
    for e in entries:
        if not e["claims"]:
            continue
        if not e.get("date_utc"):
            left_out["no_date"] += len(e["claims"])
            continue
        if not e.get("author_hash"):
            left_out["no_author"] += len(e["claims"])
            continue
        at = to_epoch(e["date_utc"])
        for c in e["claims"]:
            rows.append(
                {
                    "id": f"{e['message_id']}:{c['kind']}:{c['offset']}",
                    "msg": e["message_id"],
                    "hid": e["author_hash"],
                    "kind": c["kind"],
                    "confidence": c["confidence"],
                    "quote": c["quote"],
                    "offset": c["offset"],
                    "at": at,
                }
            )
    rows.sort(key=lambda r: (r["at"], r["id"]))
    return rows, left_out


def _chunks(rows: list[Any]) -> Iterator[list[Any]]:
    for i in range(0, len(rows), BATCH):
        yield rows[i : i + BATCH]


def write_claims(client: FalkorClient, graph: str, entries: list[dict]) -> dict:
    rows, left_out = rows_from_entries(entries)
    apply_schema(client, graph)
    for batch in _chunks(rows):
        client.query(
            graph,
            """UNWIND $rows AS r
               MERGE (a:Actor {hid: r.hid})
                 ON CREATE SET a.kind = 'human', a.source = 'mail', a.first_seen_in_org = r.at
               MERGE (src:Source {type: 'mail', ref: r.msg})
               MERGE (sp:Span {id: r.id})
                 SET sp.text = r.quote, sp.offset = r.offset, sp.at = r.at
               MERGE (src)-[:HAS]->(sp)
               MERGE (c:Claim {id: r.id})
                 SET c.kind = r.kind, c.confidence = r.confidence, c.modality = 'stated',
                     c.at = r.at
               MERGE (c)-[:FROM]->(sp)
               MERGE (a)-[:ASSERTED]->(c)""",
            {"rows": batch},
            timeout_ms=WRITE_TIMEOUT_MS,
        )
    return {"claims_written": len(rows), "left_out": left_out}
