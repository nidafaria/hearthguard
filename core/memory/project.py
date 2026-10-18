"""Per-project graph memory for Hearthguard.

Each project gets its own isolated graph in FalkorDB named hh_<project_slug>.
The slug is the lowercased project name with unsafe characters replaced by underscores.
Example: 'Left-Pad' becomes 'hh_left_pad'.

Every read and write requires an explicit project name.
There is no shared default graph for project data.
"""

import re
import time
import uuid
from typing import Any

from core.graph.client import FalkorClient
from core.graph.hashing import identifier_hash
from core.graph.schema import apply_schema

READ_TIMEOUT_MS = 10_000
WRITE_TIMEOUT_MS = 30_000


def project_slug(project: str) -> str:
    """Derive a safe slug from a project name.

    The slug is the lowercased project name with unsafe characters replaced by underscores.
    Odd names ("", "../x", "A B/C", unicode) map to a safe slug and never escape
    the graph namespace.
    """
    if not project or not str(project).strip():
        return "empty"
    # Lowercase the name
    s = str(project).strip().lower()
    # Replace any character other than [a-z0-9_] with an underscore
    slug = re.sub(r"[^a-z0-9_]", "_", s)
    return slug if slug else "empty"


def project_graph_name(project: str) -> str:
    """Return the isolated FalkorDB graph name for a project: hh_<project_slug>."""
    slug = project_slug(project)
    return f"hh_{slug}"


def write_project_claim(
    project: str,
    claim: dict[str, Any],
    client: FalkorClient | None = None,
) -> dict[str, Any]:
    """Write an accepted claim to the project's dedicated graph (hh_<project_slug>).

    Requires an explicit project name. There is no shared default graph.
    """
    if not isinstance(project, str):
        raise TypeError("project must be a string")

    graph = project_graph_name(project)
    db_client = client or FalkorClient()
    apply_schema(db_client, graph)

    claim_id = str(claim.get("id") or f"claim_{uuid.uuid4().hex[:12]}")
    kind = str(claim.get("kind", "PRESSURE"))
    confidence = float(claim.get("confidence", 1.0))
    modality = str(claim.get("modality", "stated"))
    at = int(claim.get("at", int(time.time())))
    target_hid = claim.get("target_hid")
    if target_hid is not None:
        target_hid = str(target_hid)

    author = claim.get("author") or claim.get("author_hid") or "unknown_author"
    is_hex_64 = (
        isinstance(author, str)
        and len(author) == 64
        and all(c in "0123456789abcdefABCDEF" for c in author)
    )
    author_hid = author if is_hex_64 else identifier_hash(author)

    quote = str(claim.get("quote", claim.get("text", "")))
    source_ref = str(claim.get("source_ref", claim.get("msg", "msg_001")))

    cypher = (
        "MERGE (a:Actor {hid: $author_hid}) "
        "  ON CREATE SET a.kind = 'human', a.source = 'project_memory', a.first_seen_in_org = $at "
        "FOREACH (_ IN CASE WHEN $target_hid IS NOT NULL THEN [1] ELSE [] END | "
        "  MERGE (:Actor {hid: $target_hid}) "
        ") "
        "MERGE (src:Source {type: 'claim', ref: $source_ref}) "
        "MERGE (sp:Span {id: $id}) "
        "  SET sp.text = $quote, sp.offset = 0, sp.at = $at "
        "MERGE (src)-[:HAS]->(sp) "
        "MERGE (c:Claim {id: $id}) "
        "  SET c.kind = $kind, c.confidence = $confidence, c.modality = $modality, "
        "      c.at = $at "
        "FOREACH (_ IN CASE WHEN $target_hid IS NOT NULL THEN [1] ELSE [] END | "
        "  SET c.target_hid = $target_hid "
        ") "
        "MERGE (c)-[:FROM]->(sp) "
        "MERGE (a)-[:ASSERTED]->(c) "
        "RETURN c.id AS id"
    )

    params = {
        "author_hid": author_hid,
        "target_hid": target_hid,
        "source_ref": source_ref,
        "id": claim_id,
        "quote": quote,
        "kind": kind,
        "confidence": confidence,
        "modality": modality,
        "at": at,
    }

    db_client.query(graph, cypher, params, timeout_ms=WRITE_TIMEOUT_MS)
    return {
        "project": project,
        "graph": graph,
        "claim_id": claim_id,
        "kind": kind,
        "author_hid": author_hid,
        "target_hid": target_hid,
        "at": at,
    }


def get_project_claims(
    project: str,
    client: FalkorClient | None = None,
) -> list[dict[str, Any]]:
    """Query all claims recorded for a project.

    Returns an empty list if the project graph does not exist or has no claims.
    """
    if not isinstance(project, str):
        raise TypeError("project must be a string")

    graph = project_graph_name(project)
    db_client = client or FalkorClient()

    cypher = (
        "MATCH (c:Claim) "
        "OPTIONAL MATCH (a:Actor)-[:ASSERTED]->(c) "
        "OPTIONAL MATCH (c)-[:FROM]->(sp:Span) "
        "RETURN c.id AS id, c.kind AS kind, c.confidence AS confidence, "
        "       c.modality AS modality, c.at AS at, c.target_hid AS target_hid, "
        "       a.hid AS author_hid, sp.text AS quote "
        "ORDER BY c.at ASC, c.id ASC"
    )

    try:
        res = db_client.query(graph, cypher, timeout_ms=READ_TIMEOUT_MS)
    except Exception:
        # If the graph does not exist in FalkorDB yet, query returns empty
        return []

    claims = []
    for row in res.result_set:
        claims.append(
            {
                "id": row[0],
                "kind": row[1],
                "confidence": row[2],
                "modality": row[3],
                "at": row[4],
                "target_hid": row[5],
                "author_hid": row[6],
                "quote": row[7],
            }
        )
    return claims


# Alias list_claims to match MCP tool naming
list_claims = get_project_claims


def drop_project_graph(project: str, client: FalkorClient | None = None) -> None:
    """Drop the graph associated with a project."""
    graph = project_graph_name(project)
    db_client = client or FalkorClient()
    db_client.drop(graph)
