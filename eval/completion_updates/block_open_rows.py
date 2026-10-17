"""Open-rows re-marks (branch coding/open-rows), applied by eval/completion_full.py."""

D, P = "DONE", "PARTIAL"

UPDATES = {
    "org graph: Place, PARTICIPATES_IN, RECORDED_IN": (
        D,
        "eval/populate_visibility.py writes Place, PARTICIPATES_IN and RECORDED_IN for the cached "
        "xz mail (323 messages) and git history (4,509 commits) into a GRAPH.COPY of org_xz, so "
        "the commit Actions are there to link: 96 actors, 4,832 RECORDED_IN, second run "
        "identical (eval/results/visibility_xz_org.json); also written for the finance case "
        "(packs/finance/mapping.py; tests/integration/test_visibility_graph.py); "
        "tests/unit/test_visibility_xz_org_result.py.",
    ),
}
