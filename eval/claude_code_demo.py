"""Live coding-agent demo: Claude Code calls check_trust on the SYNTHETIC tallowdate case.

Run: FALKORDB_PORT=<port> uv run python -m eval.claude_code_demo [--actor Rowan] [--action release]
Needs: the `claude` CLI signed in, FalkorDB with org_tallowdate loaded (make tallowdate-run).

The case is the fictional project tallowdate. No real project, person or pull request is involved.

What it does:
  1. Writes a throwaway MCP config (in a temp folder) that starts the hearthguard-core server, the
     same entry as `claude mcp add` gives (README, "Coding agent demo"). Your own Claude Code
     settings are not touched.
  2. Runs `claude -p` once, allowing only the check_trust tool, with a question a coding agent
     would ask before merging a pull request from a new contributor.
  3. Saves what the agent called and what came back to eval/results/claude_code_check_trust.json:
     the tool call, the tool's evidence, and the agent's answer. Nothing else is stored.

The tool returns evidence for a human, never a verdict, and writes nothing to any graph.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "mcp_servers" / "hearthguard-core" / "server.py"
RESULT = ROOT / "eval" / "results" / "claude_code_check_trust.json"
TOOL = "mcp__hearthguard-core__check_trust"
ORG = "tallowdate"
TIMEOUT_S = 300


def prompt(org: str, actor: str, action: str) -> str:
    return (
        f"A pull request from a contributor named {actor} is waiting to be merged into the "
        f"project {org}, and it touches the {action} process. Before merging, call the "
        f"check_trust tool with org={org!r}, actor={actor!r}, action={action!r}. Then tell me in "
        "three or four plain sentences what the tool returned: how long the contributor has been "
        "in the project, how many actions they have, who vouches for them, and whether the "
        "result is a verdict. Call no tool other than check_trust (loading it first is fine)."
    )


def mcp_config(port: str) -> dict:
    return {
        "mcpServers": {
            "hearthguard-core": {
                "command": "uv",
                "args": ["run", "--project", str(ROOT), "python", str(SERVER)],
                "env": {"FALKORDB_PORT": port},
            }
        }
    }


def parse_stream(lines: list[str]) -> dict:
    """The tool calls, tool results and final answer from `--output-format stream-json`."""
    calls, results, answer, model, names = [], [], "", None, {}
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            model = ev.get("model")
        content = (ev.get("message") or {}).get("content")
        if ev.get("type") == "assistant" and isinstance(content, list):
            for part in content:
                if part.get("type") == "tool_use":
                    names[part.get("id")] = part["name"]
                    calls.append({"tool": part["name"], "input": part["input"]})
        if ev.get("type") == "user" and isinstance(content, list):
            for part in content:
                if part.get("type") == "tool_result":
                    body = part.get("content")
                    if isinstance(body, list):
                        body = "".join(b.get("text", "") for b in body)
                    results.append(
                        {
                            "tool": names.get(part.get("tool_use_id")),
                            "is_error": bool(part.get("is_error")),
                            "text": body,
                        }
                    )
        if ev.get("type") == "result":
            answer = ev.get("result") or ""
    return {"model": model, "tool_calls": calls, "tool_results": results, "answer": answer}


def run(org: str, actor: str, action: str, port: str) -> dict:
    claude = shutil.which("claude")
    if not claude:
        raise SystemExit("the `claude` CLI is not on PATH")
    version = subprocess.run(
        [claude, "--version"], capture_output=True, text=True, timeout=60
    ).stdout.strip()
    with tempfile.TemporaryDirectory() as tmp:
        cfg = Path(tmp) / "mcp.json"
        cfg.write_text(json.dumps(mcp_config(port)), encoding="utf-8")
        proc = subprocess.run(
            [
                claude,
                "-p",
                prompt(org, actor, action),
                "--mcp-config",
                str(cfg),
                "--strict-mcp-config",
                "--allowedTools",
                TOOL,
                "--output-format",
                "stream-json",
                "--verbose",
                "--max-turns",
                "5",
            ],  # fmt: skip
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(ROOT),
            env={**os.environ, "FALKORDB_PORT": port, "PYTHONUTF8": "1"},
            timeout=TIMEOUT_S,
        )
    got = parse_stream(proc.stdout.splitlines())
    called = [c for c in got["tool_calls"] if c["tool"] == TOOL]
    mine = [r for r in got["tool_results"] if r["tool"] == TOOL]
    ok = bool(called) and bool(mine) and not mine[0]["is_error"]
    return {
        "synthetic": True,
        "case": f"{org} (fictional project, fictional people; docs/HEARTHGUARD.md section 3.5)",
        "client": "Claude Code",
        "claude_code_version": version,
        "model": got["model"],
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "server": "hearthguard-core, MCP over stdio, started by Claude Code from --mcp-config",
        "prompt": prompt(org, actor, action),
        "check_trust_called": bool(called),
        "ok": ok,
        "tool_calls": got["tool_calls"],
        "tool_results": got["tool_results"],
        "answer": got["answer"],
        "exit_code": proc.returncode,
        "note": "Evidence for a human. No score, no verdict, nothing written to any graph.",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", default=ORG)
    ap.add_argument("--actor", default="Rowan")
    ap.add_argument("--action", default="release")
    ap.add_argument("--out", default=str(RESULT))
    args = ap.parse_args(argv)
    port = os.environ.get("FALKORDB_PORT", "6379")
    out = run(args.org, args.actor, args.action, port)
    Path(args.out).write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"check_trust called: {out['check_trust_called']}; ok: {out['ok']}")
    print(out["answer"])
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
