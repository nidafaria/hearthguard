"""Agent handoffs via graph memory (docs/HEARTHGUARD.md §8.2, §9).

Handoffs between agents (Watcher -> Reader -> Investigator -> Skeptic -> Policy -> Liaison)
happen entirely through graph state in FalkorDB, not prompt stuffing.

Each handoff carries:
- from_agent: str
- to_agent: str
- project: str
- finding_id: str
- summary: str
- created_at: int
- status: 'open' | 'picked_up'
"""

import time
import uuid
from typing import Any

from core.graph.client import FalkorClient
from core.graph.schema import apply_schema
from core.memory.project import project_graph_name, project_slug

READ_TIMEOUT_MS = 10_000
WRITE_TIMEOUT_MS = 30_000


def write_handoff(
    from_agent: str,
    to_agent: str,
    project: str,
    finding_id: str,
    summary: str,
    created_at: int | None = None,
    handoff_id: str | None = None,
    client: FalkorClient | None = None,
) -> dict[str, Any]:
    """Write an agent handoff node into the project's graph with status 'open'.

    Idempotent MERGE on handoff_id.
    """
    if not project or not isinstance(project, str):
        raise ValueError("project must be a non-empty string")

    slug = project_slug(project)
    graph = project_graph_name(project)
    db_client = client or FalkorClient()
    apply_schema(db_client, graph)

    hid = handoff_id or f"ho_{slug}_{uuid.uuid4().hex[:12]}"
    ts = int(time.time()) if created_at is None else int(created_at)

    cypher = (
        "MERGE (h:Handoff {id: $id}) "
        "SET h.from_agent = $from_agent, "
        "    h.to_agent = $to_agent, "
        "    h.project = $project, "
        "    h.finding_id = $finding_id, "
        "    h.summary = $summary, "
        "    h.created_at = $created_at, "
        "    h.status = 'open' "
        "RETURN h.id AS id, h.status AS status"
    )
    params = {
        "id": hid,
        "from_agent": str(from_agent),
        "to_agent": str(to_agent),
        "project": str(project),
        "finding_id": str(finding_id),
        "summary": str(summary),
        "created_at": ts,
    }
    db_client.query(graph, cypher, params, timeout_ms=WRITE_TIMEOUT_MS)

    return {
        "id": hid,
        "handoff_id": hid,
        "from_agent": from_agent,
        "to_agent": to_agent,
        "project": project,
        "finding_id": finding_id,
        "summary": summary,
        "created_at": ts,
        "status": "open",
    }


def read_open_handoffs(
    agent: str,
    project: str,
    client: FalkorClient | None = None,
) -> list[dict[str, Any]]:
    """Read all open handoffs targeted to `agent` within `project`."""
    if not project or not isinstance(project, str):
        raise ValueError("project must be a non-empty string")

    graph = project_graph_name(project)
    db_client = client or FalkorClient()

    cypher = (
        "MATCH (h:Handoff) "
        "WHERE h.to_agent = $agent AND h.status = 'open' "
        "RETURN h.id AS id, h.from_agent AS from_agent, h.to_agent AS to_agent, "
        "       h.project AS project, h.finding_id AS finding_id, h.summary AS summary, "
        "       h.created_at AS created_at, h.status AS status "
        "ORDER BY h.created_at ASC, h.id ASC"
    )

    try:
        res = db_client.query(graph, cypher, {"agent": str(agent)}, timeout_ms=READ_TIMEOUT_MS)
    except Exception:
        return []

    results = []
    for row in res.result_set:
        results.append(
            {
                "id": row[0],
                "handoff_id": row[0],
                "from_agent": row[1],
                "to_agent": row[2],
                "project": row[3],
                "finding_id": row[4],
                "summary": row[5],
                "created_at": row[6],
                "status": row[7],
            }
        )
    return results


# Alias read_handoffs for MCP tool compatibility
read_handoffs = read_open_handoffs


def mark_picked_up(
    handoff_id: str,
    project: str | None = None,
    client: FalkorClient | None = None,
) -> dict[str, Any] | None:
    """Mark an open handoff as picked up.

    If project is omitted, resolves the graph from handoff_id prefix or searches hh_* graphs.
    """
    if not handoff_id or not isinstance(handoff_id, str):
        raise ValueError("handoff_id must be a non-empty string")

    db_client = client or FalkorClient()
    candidate_graphs: list[str] = []

    if project:
        candidate_graphs.append(project_graph_name(project))
    else:
        # Attempt to infer from "ho_<slug>_<uuid>" format
        if handoff_id.startswith("ho_"):
            parts = handoff_id[3:].rsplit("_", 1)
            if parts:
                candidate_graphs.append(f"hh_{parts[0]}")

        # Fallback: search all existing hh_* graphs in FalkorDB
        try:
            raw_graphs = db_client.db.execute_command("GRAPH.LIST")
            existing = [g if isinstance(g, str) else g.decode() for g in raw_graphs]
            for g in existing:
                if g.startswith("hh_") and g not in candidate_graphs:
                    candidate_graphs.append(g)
        except Exception:
            pass

    cypher = (
        "MATCH (h:Handoff {id: $id}) "
        "SET h.status = 'picked_up' "
        "RETURN h.id AS id, h.status AS status, h.to_agent AS to_agent, h.project AS project"
    )

    for graph in candidate_graphs:
        try:
            res = db_client.query(graph, cypher, {"id": handoff_id}, timeout_ms=WRITE_TIMEOUT_MS)
            if res.result_set:
                row = res.result_set[0]
                return {
                    "id": row[0],
                    "handoff_id": row[0],
                    "status": row[1],
                    "to_agent": row[2],
                    "project": row[3],
                }
        except Exception:
            continue

    return None
