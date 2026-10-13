"""Block F re-marks, applied by eval/completion_full.py. Each entry names its evidence."""

D, P = "DONE", "PARTIAL"

UPDATES = {
    "org graph: Hardening, Task, AgentStep": (
        D,
        "core/board/hardening.py (Hardening MERGE on run_ref+step, FOR Org), core/board/board.py "
        "(Task), core/agents/agent_step.py (AgentStep); tests/integration/test_board_core.py on a "
        "real FalkorDB.",
    ),
    "Task board with leases, stale-result rejection, requests": (
        D,
        "core/board/board.py (8.2 claim query, 30 s lease, expired lease reopens, stale result "
        "requeued by input_version, unique note key), core/board/requests.py (objection -> "
        "request -> finding released); tests/integration/test_board_core.py, "
        "tests/unit/test_board_rules.py. Not yet called by the Investigator or Skeptic agents.",
    ),
    "Guardrails: circuit breaker, bounded HOLD, re-plan limits": (
        D,
        "core/agents/guardrails.py (layout check, named failure types, <=2 re-plans, time limit, "
        "3-strike breaker, bounded HOLD, no LLM on the abort path); tests/unit/"
        "test_guardrails_policy.py; eval/results/faults_run.json. The breaker is in memory, not "
        "saved across a restart, and no LLM planner calls run_guarded yet.",
    ),
    "Working memory (AgentStep, task board)": (
        D,
        "core/agents/agent_step.py (log_step, resume_state); tests/integration/test_board_core.py "
        "(a second client resumes a crashed agent's task from the graph). A docker restart of "
        "the container was also checked by hand with a named volume; that check is not a test.",
    ),
    "Determinism, race and concurrency tests": (
        D,
        "eval/verify_determinism.py -> eval/results/determinism_run.json (5 orderings, different "
        "claim orders, identical findings equal to the fixture answers); eval/race.py -> "
        "race_run.json (0 duplicate claims, 0 duplicate notes); eval/concurrency.py -> "
        "concurrency_run.json (throughput and p50/p95 on this machine only); tests/determinism, "
        "tests/race. The make targets are not wired yet.",
    ),
    "Resilience (`make faults`)": (
        D,
        "eval/faults.py -> eval/results/faults_run.json: all 9 failure types incl. LLM offline "
        "(real LLMClient with no key) end in a bounded HOLD; circuit breaker; structural tasks "
        "finish with the LLM offline; tests/faults/test_faults.py. Five of the nine are injected "
        "by real causes, four are raised by the test plan (the JSON says which). The make "
        "target is not wired yet.",
    ),
}
