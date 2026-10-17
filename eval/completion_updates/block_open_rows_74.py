"""Open-rows re-marks (branch coding/open-rows), applied by eval/completion_full.py."""

P = "PARTIAL"

UPDATES = {
    "Who-saw-what memory": (
        P,
        "core/memory/who_saw.py (PARTICIPATES_IN, WATCHES {since}, already_acknowledged); "
        "tests/integration/test_who_saw.py. PARTICIPATES_IN is now filled from the cached xz mail "
        "and git: 96 actors, second run identical (eval/results/visibility_xz_org.json, on a copy "
        "of org_xz). Not DONE: WATCHES has no public source for xz, and nothing calls "
        "already_acknowledged before a send (eval/results/blockers_open_rows.md).",
    ),
}
