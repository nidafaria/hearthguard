"""A coding agent asks check_trust before a merge (spec §4.3, §12.1).

Run: uv run python -m eval.merge_gate --org tallowdate --actor <name or hid> [--action release]

Starts the hearthguard-core MCP server as a child process over stdio, lists its tools, and calls
check_trust the way a coding agent's MCP client would. The answer is evidence for a human, never a
verdict, and nothing is written to any graph. Writes eval/results/check_trust_demo.json. This
script is the client; it is not Claude Code, so the Claude Code wiring (row 99) is a separate
step (docs/mcp/claude_code_config.json shows the entry).
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "mcp_servers" / "hearthguard-core" / "server.py"
RESULT = ROOT / "eval" / "results" / "check_trust_demo.json"
SYNTHETIC_ORGS = {"tallowdate"}


def _payload(result) -> dict:
    """The tool's dict, from structured content or from the one JSON text block."""
    if getattr(result, "structured_content", None):
        sc = result.structured_content
        return sc.get("result", sc) if isinstance(sc, dict) else sc
    return json.loads(result.content[0].text)


async def ask(org: str, actor: str, action: str) -> dict:
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER)],
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        cwd=str(ROOT),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = sorted(t.name for t in listed.tools)
            if "check_trust" not in names:
                raise RuntimeError("the server does not offer check_trust")
            result = await session.call_tool(
                "check_trust", {"org": org, "actor": actor, "action": action}
            )
            if result.is_error:
                raise RuntimeError(f"check_trust returned an error: {result.content}")
            return {"tools_listed": names, "evidence": _payload(result)}


def run(org: str, actor: str, action: str) -> dict:
    got = asyncio.run(ask(org, actor, action))
    return {
        "question": "A merge by this author is pending. What does check_trust say first?",
        "transport": "MCP over stdio, server started as a child process",
        "client": "eval/merge_gate.py (not Claude Code)",
        "org": org,
        "synthetic": org in SYNTHETIC_ORGS,
        "action": action,
        "tools_listed": got["tools_listed"],
        "evidence": got["evidence"],
        "note": "Evidence for a human. No score, no verdict, nothing written to any graph.",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", required=True)
    ap.add_argument("--actor", required=True)
    ap.add_argument("--action", default="release")
    ap.add_argument("--out", default=str(RESULT))
    args = ap.parse_args(argv)
    out = run(args.org, args.actor, args.action)
    Path(args.out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
