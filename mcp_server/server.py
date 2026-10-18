"""Hearthguard MCP Server providing per-project memory, handoffs, and custody recall.

Tools:
- list_claims(project)
- write_handoff(from_agent, to_agent, project, finding_id, summary)
- read_handoffs(agent, project)
- recall_custody(project)
"""

import sys
from pathlib import Path

# Ensure repository root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from core.graph.client import FalkorClient  # noqa: E402
from core.memory.custody import recall_custody_baseline  # noqa: E402
from core.memory.handoff import read_open_handoffs  # noqa: E402
from core.memory.handoff import write_handoff as do_write_handoff  # noqa: E402
from core.memory.project import get_project_claims, project_graph_name  # noqa: E402

server = MCPServer(
    "hearthguard",
    instructions="Hearthguard per-project memory, agent handoffs, and custody recall.",
)


@server.tool()
def list_claims(project: str) -> list[dict]:
    """List all claims recorded in the project's graph memory."""
    client = FalkorClient()
    return get_project_claims(project=project, client=client)


@server.tool()
def write_handoff(
    from_agent: str,
    to_agent: str,
    project: str,
    finding_id: str,
    summary: str,
) -> dict:
    """Record an agent handoff in the project's graph memory."""
    client = FalkorClient()
    return do_write_handoff(
        from_agent=from_agent,
        to_agent=to_agent,
        project=project,
        finding_id=finding_id,
        summary=summary,
        client=client,
    )


@server.tool()
def read_handoffs(agent: str, project: str) -> list[dict]:
    """Read all open handoffs for an agent in a project."""
    client = FalkorClient()
    return read_open_handoffs(agent=agent, project=project, client=client)


@server.tool()
def recall_custody(project: str) -> list[dict]:
    """Recall who held custody for a project from graph memory."""
    client = FalkorClient()
    graph = (
        project
        if (project.startswith("hh_") or project.startswith("org_"))
        else project_graph_name(project)
    )
    return recall_custody_baseline(client=client, graph=graph)


if __name__ == "__main__":
    server.run(transport="stdio")
