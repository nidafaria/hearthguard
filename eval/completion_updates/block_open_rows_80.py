"""Open-rows re-marks (branch coding/open-rows), applied by eval/completion_full.py."""

P = "PARTIAL"

UPDATES = {
    "Learning proof": (
        P,
        "`make verify-learning` and `make chaos SEED=n` are wired (Makefile, make.ps1) and rerun "
        "to the saved files unchanged: eval/results/learning_verify.json, "
        "learning_chaos_seed{1,2,3,4,5,7,42}.json. Not DONE: seeds with the same pattern give the "
        "same exception, and whether 'a different exception' means a different pattern is the "
        "spec owner's call (eval/results/blockers_E.md, row 80).",
    ),
}
