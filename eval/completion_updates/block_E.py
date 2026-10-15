# ruff: noqa: E501
"""Block E re-marks, applied by eval/completion_full.py. Each entry names its evidence."""

D, P = "DONE", "PARTIAL"

UPDATES = {
    "playbook graph": (
        P,
        "core/playbook/store.py (DetectorSpec hash, Exception nodes with state, agreements and gate "
        "numbers; no org data); tests/integration/test_learning_store.py. Compiled investigation "
        "plans are not built (eval/results/blockers_E.md, row 43).",
    ),
    "Learned exceptions with safety rules and regression gate": (
        P,
        "core/learning/ (templates, filler, safety, gate, states, pipeline); tests/unit/"
        "test_learning_*.py (39 passing); docs/decisions/0007. The gate is a worst-case replay on "
        "eval/results/redteam_xz.json; the filler is a fixed table, not the LLM of spec 8.3. "
        "Adopted does not act yet (eval/results/blockers_E.md, row 66).",
    ),
    "Owner memory": (
        D,
        "core/agents/inbox_graph.py (situation_of, _apply_owner_memory, OwnerDecision.situation): a "
        "dismissed situation is held back until a Claim later than the dismissal arrives; "
        "tests/integration/test_learning_memory.py (4 tests, real FalkorDB).",
    ),
    "Learning proof (`verify-learning`, `chaos`)": (
        P,
        "eval/verify_learning.py -> eval/results/learning_verify.json; eval/chaos.py -> "
        "eval/results/learning_chaos_seed{1,2,3,4,5,7,42}.json. The make targets are not wired yet, "
        "and seeds with the same pattern give the same exception (eval/results/blockers_E.md, row 80).",
    ),
    "Simulate a fix button": (
        P,
        "Unchanged in this block. Live simulate on GRAPH.COPY (core/agents/simulate_fix.py). "
        "eval/results/hardening_redteam_xz.json now exists, but tests/integration/test_inbox_loop.py "
        "asserts NOT COMPUTED for xz and cannot be edited (eval/results/blockers_E.md, row 102).",
    ),
    "It's fine button and learning result in thread": (
        P,
        "api/inbox_actions.py dismiss runs the learning step and returns the result; "
        "ui/src/Thread.tsx shows it; tests/integration/test_learning_thread.py (8 passing). The "
        "browser check is not run and nothing is applied (eval/results/blockers_E.md, row 104).",
    ),
    "Playbook screen": (
        P,
        "ui/src/Playbook.tsx and the #/playbook route in ui/src/App.tsx; tsc --noEmit clean, vitest "
        "31 passing. No browser check and no test of the screen itself (eval/results/blockers_E.md, "
        "row 120).",
    ),
}
