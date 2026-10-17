"""The Claude Code demo's parsing and its saved result. No `claude` CLI and no database needed."""

import json
from pathlib import Path

from eval import claude_code_demo as demo

SAVED = Path(demo.RESULT)


def stream(*events: dict) -> list[str]:
    return [json.dumps(e) for e in events]


def test_parse_stream_finds_the_call_the_result_and_the_answer():
    lines = stream(
        {"type": "system", "subtype": "init", "model": "m"},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "id": "u1", "name": demo.TOOL, "input": {"org": "t"}}
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {"type": "tool_result", "tool_use_id": "u1", "content": [{"text": "{}"}]}
                ]
            },
        },
        {"type": "result", "result": "done"},
    )
    got = demo.parse_stream(lines + ["not json"])
    assert got["model"] == "m"
    assert got["tool_calls"] == [{"tool": demo.TOOL, "input": {"org": "t"}}]
    assert got["tool_results"] == [{"tool": demo.TOOL, "is_error": False, "text": "{}"}]
    assert got["answer"] == "done"


def test_the_config_starts_the_core_server_on_the_given_port():
    cfg = demo.mcp_config("6413")["mcpServers"]["hearthguard-core"]
    assert cfg["env"] == {"FALKORDB_PORT": "6413"}
    assert cfg["args"][-1].endswith("server.py")


def test_the_saved_run_is_the_synthetic_case_and_called_check_trust():
    saved = json.loads(SAVED.read_text(encoding="utf-8"))
    assert saved["synthetic"] is True and saved["client"] == "Claude Code"
    assert saved["check_trust_called"] is True and saved["ok"] is True
    names = [c["tool"] for c in saved["tool_calls"]]
    assert demo.TOOL in names and set(names) <= {demo.TOOL, "ToolSearch"}
    mine = [r for r in saved["tool_results"] if r["tool"] == demo.TOOL]
    assert "verdict" not in json.loads(mine[0]["text"])
    assert "@" not in json.dumps(saved)
