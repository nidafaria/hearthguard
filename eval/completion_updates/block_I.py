"""Block I re-marks, applied by eval/completion_full.py. Each entry names its evidence."""

D, P = "DONE", "PARTIAL"

UPDATES = {
    "Memory ablation (`make ablation-memory`)": (
        D,
        "eval/ablation_memory.py (full vs forgetful 90 / 30 days, same 100 campaigns + 20 clean, "
        "frozen detectors unchanged) writes eval/results/ablation_memory.json; "
        "tests/integration/test_ablation_memory.py on a real FalkorDB. Run as `uv run python -m "
        "eval.ablation_memory`; the Makefile target is for the lead to wire. Published as "
        "measured: forgetting lowers detection (0.88 full, 0.82 at 90 days, 0.60 at 30 days) and "
        "flags 20 of 20 clean campaigns under forgetful memory against 1 of 20 under full.",
    ),
    "Algorithm ablation (`make ablation-algos`)": (
        D,
        "eval/ablation_algos.py (Vouch components, SPpaths, maxFlow off one at a time) writes "
        "eval/results/ablation_algos.json; tests/integration/test_ablation_algos.py. Run as `uv "
        "run python -m eval.ablation_algos`; the Makefile target is for the lead to wire. "
        "Published as measured: SPpaths off and maxFlow off tie the baseline (SPpaths is never "
        "called by the decision path); Vouch without components raises detection 0.88 to 0.90 "
        "with no change in false alarms on a clean set that has no vouch claims, so it does not "
        "show that the component step helps.",
    ),
    "hearthguard-core MCP server (9 tools)": (
        D,
        "mcp_servers/hearthguard-core/{server,tools}.py registers check_trust, takeover_cost, "
        "guardians, org_normal, trust_path, visibility_gaps, simulate_hardening, why, claims_for "
        "(read-only, hashed ids, as-of T); tests/integration/test_mcp_core.py on a real FalkorDB "
        "(including a tool-list check and a no-write check), tests/unit/test_mcp_tools.py. "
        "visibility_gaps and why answer for the saved xz run and the two inbox cases only.",
    ),
    "pack-oss MCP server": (
        D,
        "mcp_servers/pack-oss/{server,tools}.py registers release_path, grant_history, "
        "ecosystem_overlap, upstream_context (read-only); tests/integration/test_mcp_oss.py on a "
        "real FalkorDB (tool-list check, no-write check). grant_history is empty for xz because "
        "git records no grants (eval/results/xz_grants_unknown.json).",
    ),
    "Patience curve": (
        D,
        "ui/src/Patience.tsx draws detection rate and lead time against attacker patience, full vs "
        "forgetful memory, from eval/results/ablation_memory.json (and says NOT COMPUTED when the "
        "file is absent); ui/src/Patience.test.tsx and the existing ui/src/screens.test.tsx pass.",
    ),
}
