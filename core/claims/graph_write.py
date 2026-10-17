"""Write the Reader's accepted claims into an org graph (docs/HEARTHGUARD.md §6.1, text part).

    (:Source {type, ref})-[:HAS]->(:Span {text, offset, at})
    (:Claim {id, kind, confidence, modality, at, target_hid})-[:FROM]->(:Span)
    (:Actor)-[:ASSERTED]->(:Claim)

MERGE on unique keys only, so running it twice changes nothing. Claim.id is
"<message id>:<kind>:<offset>". An Actor that already exists (for example a git author with the
same hashed email) is left exactly as it is. An Actor that does not exist yet is created with
`source = 'mail'` and `first_seen_in_org` = the time of the first claim written for them, so
history from the mailing list is never presented as older than what we saw.
The span text is the quote (at most 25 words of the cleaned message), never a whole message.
Candidate targets for VOUCH claims land in Claim.target_hid.
"""

import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from core.graph.client import FalkorClient
from core.graph.schema import apply_schema

BATCH = 300
WRITE_TIMEOUT_MS = 60_000

# Locations where agent 2 (AI reading) might produce candidate targets
AGENT2_TARGET_PATHS = [
    Path("eval/results/candidate_targets.json"),
    Path("eval/results/reader_vouch_targets.json"),
    Path("../hh-t2-reader/eval/results/candidate_targets.json"),
    Path("../hh-t2-reader/eval/results/reader_full_run.json"),
]


def _load_agent2_targets() -> dict[str, str]:
    """Load candidate targets from agent 2's output when available."""
    for p in AGENT2_TARGET_PATHS:
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    if "targets" in data and isinstance(data["targets"], dict):
                        return data["targets"]
                    if "messages" in data and isinstance(data["messages"], list):
                        mapping = {}
                        for m in data["messages"]:
                            mid = m.get("message_id")
                            for cl in m.get("claims", []):
                                tgt = (
                                    cl.get("target_hid")
                                    or cl.get("target")
                                    or cl.get("candidate")
                                )
                                if tgt:
                                    mapping[mid] = str(tgt)
                        if mapping:
                            return mapping
                    return {k: str(v) for k, v in data.items() if isinstance(v, (str, int))}
            except Exception:
                continue
    return {}


def resolve_target_hid(c: dict, e: dict) -> str | None:
    """Resolve candidate target for a claim.

    Target resolution comes from the claim data or the Agent 2 reader output only.
    If missing, returns None so Vouch evaluates to NOT_COMPUTED.
    """
    # 1. Direct explicit field in the claim
    target = c.get("target_hid") or c.get("target") or c.get("candidate")
    if target:
        return str(target)

    # 2. Check agent 2's output when it exists
    agent2_targets = _load_agent2_targets()
    msg_id = e.get("message_id")
    if msg_id and msg_id in agent2_targets:
        return agent2_targets[msg_id]

    return None


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
        for idx, c in enumerate(e["claims"]):
            target_hid = resolve_target_hid(c, e)
            offset = c.get("offset", idx)
            rows.append(
                {
                    "id": f"{e['message_id']}:{c['kind']}:{offset}",
                    "msg": e["message_id"],
                    "hid": e["author_hash"],
                    "kind": c["kind"],
                    "confidence": c.get("confidence", 1.0),
                    "quote": c.get("quote", ""),
                    "offset": offset,
                    "at": at,
                    "target_hid": target_hid,
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
               FOREACH (_ IN CASE WHEN r.target_hid IS NOT NULL THEN [1] ELSE [] END |
                 MERGE (:Actor {hid: r.target_hid})
               )
               MERGE (src:Source {type: 'mail', ref: r.msg})
               MERGE (sp:Span {id: r.id})
                 SET sp.text = r.quote, sp.offset = r.offset, sp.at = r.at
               MERGE (src)-[:HAS]->(sp)
               MERGE (c:Claim {id: r.id})
                 SET c.kind = r.kind, c.confidence = r.confidence, c.modality = 'stated',
                     c.at = r.at
               FOREACH (_ IN CASE WHEN r.target_hid IS NOT NULL THEN [1] ELSE [] END |
                 SET c.target_hid = r.target_hid
               )
               MERGE (c)-[:FROM]->(sp)
               MERGE (a)-[:ASSERTED]->(c)""",
            {"rows": batch},
            timeout_ms=WRITE_TIMEOUT_MS,
        )
    return {"claims_written": len(rows), "left_out": left_out}
