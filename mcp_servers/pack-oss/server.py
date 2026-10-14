"""pack-oss MCP server (docs/HEARTHGUARD.md §12.1): four read-only tools for the OSS pack.

Run (stdio):  uv run python mcp_servers/pack-oss/server.py
The directory name has a hyphen, so it is run as a script. The logic is in tools.py beside this
file; the tests import it. FalkorDB host and port come from FALKORDB_HOST and FALKORDB_PORT.
No tool writes.
"""

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from core.graph.client import FalkorClient  # noqa: E402

_spec = importlib.util.spec_from_file_location("pack_oss_tools", HERE / "tools.py")
tools = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tools)

server = MCPServer(
    "pack-oss", instructions="Read-only questions about a package's releases, grants and upstream."
)


@server.tool()
def release_path(org: str, version: str) -> dict:
    """The path this release took, against the project's normal. Read-only."""
    return tools.release_path(FalkorClient(), org, version)


@server.tool()
def grant_history(org: str) -> dict:
    """Who was granted which privilege and when (hashed ids), where documented. Read-only."""
    return tools.grant_history(FalkorClient(), org)


@server.tool()
def ecosystem_overlap(ecosystem: str) -> dict:
    """How many identities appear in more than one place of an ecosystem graph. Read-only."""
    return tools.ecosystem_overlap(FalkorClient(), ecosystem)


@server.tool()
def upstream_context(package: str, version: str) -> dict:
    """Before accepting a dependency upgrade: release path, takeover cost and guardians."""
    return tools.upstream_context(FalkorClient(), package, version)


if __name__ == "__main__":
    server.run()
