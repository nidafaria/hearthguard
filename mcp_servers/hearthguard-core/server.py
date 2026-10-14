"""hearthguard-core MCP server (docs/HEARTHGUARD.md §12.1): nine read-only tools.

Run (stdio):  uv run python mcp_servers/hearthguard-core/server.py
The directory name has a hyphen, so it is run as a script and not imported as a package. The tool
logic is in tools.py beside this file; the tests import it. FalkorDB host and port come from
FALKORDB_HOST and FALKORDB_PORT. No tool writes to an org graph, and there is no send path here:
the Liaison's approval-token send is not exposed through this server.
"""

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from core.graph.client import FalkorClient  # noqa: E402

_spec = importlib.util.spec_from_file_location("hearthguard_core_tools", HERE / "tools.py")
tools = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tools)

server = MCPServer(
    "hearthguard-core",
    instructions="Read-only questions about who can take over a project and how it would look.",
)


@server.tool()
def check_trust(org: str, actor: str, action: str) -> dict:
    """Evidence about an actor before an action: history, vouches, holdings, trust path to `action`.

    `action` is a privilege kind such as release. Evidence for a human, not a verdict. Read-only.
    """
    return tools.check_trust(FalkorClient(), org, actor, action)


@server.tool()
def takeover_cost(org: str, privilege: str) -> dict:
    """The fewest approvals an outsider must win to get `privilege`. Provisional rule. Read-only."""
    return tools.takeover_cost(FalkorClient(), org, privilege)


@server.tool()
def guardians(org: str, privilege: str) -> dict:
    """The fewest people on every route from an outsider to `privilege`. Read-only."""
    return tools.guardians_(FalkorClient(), org, privilege)


@server.tool()
def org_normal(org: str) -> dict:
    """The remembered normal metrics for this org. Read-only."""
    return tools.org_normal(FalkorClient(), org)


@server.tool()
def trust_path(org: str, actor: str, privilege: str) -> dict:
    """The shortest trust path from `actor` to `privilege`. NO PATH is a result. Read-only."""
    return tools.trust_path_(FalkorClient(), org, actor, privilege)


@server.tool()
def visibility_gaps(decision: str) -> dict:
    """Who could have seen what before a downstream decision, roles only. Read-only."""
    return tools.visibility_gaps(decision)


@server.tool()
def simulate_hardening(org: str, step: str) -> dict:
    """One hardening step on a copy of the graph: cost and guardians before and after."""
    return tools.simulate_hardening(FalkorClient(), org, step)


@server.tool()
def why(finding_id: str) -> dict:
    """A finding, the evidence behind it, each quote and its source link. Read-only."""
    return tools.why(FalkorClient(), finding_id)


@server.tool()
def claims_for(org: str, actor: str, window: int = 90) -> dict:
    """The claims `actor` made in the last `window` days, each with its quote and link."""
    return tools.claims_for(FalkorClient(), org, actor, window)


if __name__ == "__main__":
    server.run()
