"""Open-rows re-marks (branch coding/open-rows), applied by eval/completion_full.py."""

D = "DONE"

UPDATES = {
    "Owner memory": (
        D,
        "OwnerDecision written once per finding (core/agents/inbox_graph.py record_dismissal); a "
        "dismissed situation is held back in a later quarter and returns only with a Claim newer "
        "than the dismissal, as of T (_apply_owner_memory); "
        "tests/integration/test_learning_memory.py (4 passing: held back, new evidence reopens, "
        "different situation not held, later dismissal does not hold back an earlier quarter).",
    ),
}
