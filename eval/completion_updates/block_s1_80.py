"""Row 80 re-mark (branch coding/s1-defaults), applied by eval/completion_full.py."""

D = "DONE"

UPDATES = {
    "Learning proof": (
        D,
        "default chosen for submission, not final (docs/decisions/0007, 2026-10-18): a different "
        "exception means a different pattern. `make verify-learning` and `make chaos SEED=n` rerun "
        "to the saved files; seeds 1-4 share the bots exception, seeds 5/42 and 7 give two other "
        "patterns, each with its own id; tests/unit/test_chaos_default_0007.py (2 passing).",
    ),
}
