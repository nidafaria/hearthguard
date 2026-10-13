"""Block H re-marks, applied by eval/completion_full.py. Each entry names its evidence."""

D, P = "DONE", "PARTIAL"

UPDATES = {
    "Core free of domain code; OSS pack and finance pack separated": (
        P,
        "packs/finance/ now exists beside packs/oss/; core imports nothing from packs/ "
        "(tests/unit/test_pack_oss.py) and packs/finance imports nothing from packs.oss "
        "(tests/unit/test_finance_pack.py). Not DONE: core still holds OSS words in "
        "core/normal/metrics.py (commit, release) and the per-pack property table in "
        "core/detectors/bypass.py. See eval/results/blockers_H.md row 17.",
    ),
    "`make verify-packs` (finance runs with OSS pack removed)": (
        D,
        "eval/verify_packs.py runs the Northbridge case in a temp tree with no packs/oss and "
        "compares it to the run with the pack present: eval/results/finance_verify_packs.json "
        "(passed); tests/integration/test_finance_verify_packs.py. Run as `uv run python -m "
        "eval.verify_packs`; the Makefile target is for the lead to wire.",
    ),
    "Finance pack (parsers, mapping, vocabulary, normal path)": (
        D,
        "packs/finance/{pack,parse,mapping,synthetic,tools}.py; data/synthetic/northbridge.json "
        "(93 synthetic records); tests/unit/test_finance_pack.py, "
        "tests/integration/test_finance_case.py on a real FalkorDB.",
    ),
    "org graph: Place, PARTICIPATES_IN, RECORDED_IN": (
        P,
        "Written for the finance case (packs/finance/mapping.py; tests/integration/"
        "test_visibility_graph.py) and for the cached xz mail (eval/populate_visibility.py: 323 "
        "messages, 28 authors, 28 PARTICIPATES_IN, 323 RECORDED_IN, second run identical: "
        "eval/results/visibility_xz.json). The cached xz git part was not run: it needs "
        "HEARTHGUARD_HASH_SALT (eval/results/blockers_H.md row 35).",
    ),
    "Vector index on Span and full-text index on Span.text": (
        D,
        "core/graph/schema.py apply_schema creates both (verified DDL); eval/vector_index.py, "
        "eval/results/vector_index_run.json; tests/integration/test_vector_index.py. No real Span "
        "is embedded yet: the pinned sentence-transformers model is not installed "
        "(eval/results/blockers_H.md row 45).",
    ),
    "Who-saw-what memory": (
        P,
        "core/memory/who_saw.py (PARTICIPATES_IN, WATCHES, RECORDED_IN writers, "
        "already_acknowledged) is now filled from the finance case and the cached xz mail "
        "(eval/results/visibility_xz.json). Cached xz git is not filled (salt missing), and "
        "no Liaison caller of already_acknowledged exists yet.",
    ),
    "Finance pack case (Northbridge, Kestrel), scripted": (
        P,
        "eval/northbridge_case.py, eval/results/finance_northbridge_case.json: Rush FIRED, "
        "Bypass FIRED on channel, callback, approvers; Lone keeper FLAG_SET; takeover cost 1 -> 2 "
        "after restoring two-person approval on a GRAPH.COPY; tests/integration/"
        "test_finance_case.py. Pressure, Vouch and the Liaison note are NOT COMPUTED: they need "
        "the Reader and the Liaison, which are LLM steps (eval/results/blockers_H.md row 94).",
    ),
    "pack-finance MCP server": (
        D,
        "mcp_servers/pack-finance/server.py registers vendor_change_path and approval_history "
        "(logic in packs/finance/tools.py); tests/integration/test_finance_mcp.py on a real "
        "FalkorDB, including a read-only check and a tool-list check.",
    ),
}
