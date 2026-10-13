"""pack-finance MCP server (docs/HEARTHGUARD.md §12.1): two read-only tools for the finance pack.

Run (stdio):  uv run python mcp_servers/pack-finance/server.py
The directory name has a hyphen, so it is run as a script and not imported as a package. The tool
logic lives in packs/finance/tools.py, which the tests import. FalkorDB host and port come from
FALKORDB_HOST and FALKORDB_PORT, as for every client in this repo. No tool writes.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from core.graph.client import FalkorClient  # noqa: E402
from packs.finance import tools  # noqa: E402

server = MCPServer(
    "pack-finance",
    instructions="Read-only questions about vendor bank-detail changes in a finance org graph.",
)


@server.tool()
def vendor_change_path(org: str, vendor: str, change: str = "bank_change") -> dict:
    """The path the latest change of this kind for this vendor took, against the company's normal.

    `org` is the org id (the graph is org_<id>); `vendor` is the vendor id; `change` is an action
    kind such as bank_change. Read-only.
    """
    return tools.vendor_change_path(FalkorClient(), org, vendor, change)


@server.tool()
def approval_history(org: str, vendor: str) -> dict:
    """Who approved each earlier bank-detail change for this vendor, and how. Read-only."""
    return tools.approval_history(FalkorClient(), org, vendor)


if __name__ == "__main__":
    server.run()
