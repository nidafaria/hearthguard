"""Open-rows re-marks (branch coding/open-rows), applied by eval/completion_full.py."""

D = "DONE"

UPDATES = {
    "Coding agent `check_trust` before a merge": (
        D,
        "eval/merge_gate.py starts the hearthguard-core MCP server over stdio, lists its nine "
        "tools and calls check_trust for a pending merge's author: evidence, no verdict, nothing "
        "written (eval/results/check_trust_demo.json, on the SYNTHETIC tallowdate case); "
        "tests/integration/test_merge_gate.py on a real FalkorDB. The client is this script, not "
        "Claude Code; wiring Claude Code itself is row 99 (docs/mcp/claude_code_config.json).",
    ),
}
