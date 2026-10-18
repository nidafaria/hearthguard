"""Integration test for mcp_server/server.py over stdio (Step C).

Starts the server over stdio, calls all four tools:
- list_claims(project)
- write_handoff(from_agent, to_agent, project, finding_id, summary)
- read_handoffs(agent, project)
- recall_custody(project)
Checks each result against direct FalkorDB graph contents.
"""

import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from core.graph.client import FalkorClient
from core.memory.custody import record_custody_baseline
from core.memory.project import drop_project_graph, project_graph_name, write_project_claim

ROOT = Path(__file__).resolve().parents[2]
SERVER_SCRIPT = ROOT / "mcp_server" / "server.py"


@pytest.fixture
def client() -> FalkorClient:
    return FalkorClient()


@pytest.mark.asyncio
async def test_mcp_server_stdio_four_tools(client):
    project = "mcp_stdio_test"
    drop_project_graph(project, client)
    graph = project_graph_name(project)

    # 1. Seed graph contents directly
    claim_id = "claim-mcp-001"
    write_project_claim(
        project,
        {
            "id": claim_id,
            "kind": "PRESSURE",
            "author": "alice@example.invalid",
            "quote": "Release needed ASAP",
            "confidence": 0.9,
            "at": 1710000000,
        },
        client,
    )

    record_custody_baseline(
        client,
        graph=graph,
        custodian_hid="custodian_001",
        custodian_name="Alice Keeper",
        privilege="release",
        at=1700000000,
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
        env=env,
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Verify tools are registered
                tools_list = await session.list_tools()
                tool_names = [t.name for t in tools_list.tools]
                assert "list_claims" in tool_names
                assert "write_handoff" in tool_names
                assert "read_handoffs" in tool_names
                assert "recall_custody" in tool_names

                # Tool 1: list_claims
                res1 = await session.call_tool("list_claims", arguments={"project": project})
                assert res1.content
                # FastMCP / MCPServer returns structured content in res1.content
                text_or_val = res1.content[0].text
                assert claim_id in text_or_val
                assert "PRESSURE" in text_or_val

                # Tool 2: write_handoff
                res2 = await session.call_tool(
                    "write_handoff",
                    arguments={
                        "from_agent": "Watcher",
                        "to_agent": "Investigator",
                        "project": project,
                        "finding_id": "find_mcp_99",
                        "summary": "Sudden commit burst from unvouched account",
                    },
                )
                assert res2.content
                text2 = res2.content[0].text
                assert "find_mcp_99" in text2
                assert "open" in text2

                # Verify against graph contents
                q_handoff = client.query(
                    graph,
                    "MATCH (h:Handoff {finding_id: 'find_mcp_99'}) "
                    "RETURN h.id, h.summary, h.status",
                )
                assert len(q_handoff.result_set) == 1
                assert q_handoff.result_set[0][1] == "Sudden commit burst from unvouched account"
                assert q_handoff.result_set[0][2] == "open"

                # Tool 3: read_handoffs
                res3 = await session.call_tool(
                    "read_handoffs",
                    arguments={"agent": "Investigator", "project": project},
                )
                assert res3.content
                text3 = res3.content[0].text
                assert "find_mcp_99" in text3
                assert "Watcher" in text3

                # Tool 4: recall_custody
                res4 = await session.call_tool(
                    "recall_custody",
                    arguments={"project": project},
                )
                assert res4.content
                text4 = res4.content[0].text
                assert "custodian_001" in text4
                assert "Alice Keeper" in text4

    finally:
        drop_project_graph(project, client)
