# ruff: noqa: E501 (evidence strings are long by design)
"""Block A re-marks for the note loop (web inbox). Read by eval/completion_full.py.

Each entry: row item prefix -> (status, evidence). P = PARTIAL, D = DONE. Reasons for every
PARTIAL are in eval/results/blockers_a.md.
"""

D, P = "DONE", "PARTIAL"
TESTS = (
    "tests/unit/test_inbox_rules.py; tests/integration/test_inbox_loop.py; "
    "tests/integration/test_why_quote_link.py"
)
BROWSER = (
    "eval/results/inbox_browser_check.json; eval/results/inbox_screens/xz_2021-Q4_all_controls.png"
)

UPDATES = {
    "Maintainer private note": (
        P,
        "web inbox only: core/agents/liaison.py, api/inbox_actions.py; no Slack DM; "
        f"tests: {TESTS}; blockers_a.md",
    ),
    "org graph: Finding, Gap, Objection, Request, Note, Draft, OwnerDecision, BACKUP": (
        P,
        "core/agents/inbox_graph.py writes Finding, Note, Draft, OwnerDecision, BACKUP, Gap "
        "(xz from eval/results/ecosystem_gaps.json), Hardening; Objection and Request writers "
        "exist but no Skeptic source and no test; blockers_a.md",
    ),
    "`why` query": (
        D,
        "core/agents/why.py run_why (spec 7.6 Cypher through core/graph/ro_guard.py, timeout); "
        f"tests: tests/integration/test_why_quote_link.py, {TESTS}",
    ),
    "Investigator": (
        P,
        "core/agents/investigator.py fixed tool router, no LLM (docs/decisions/0008-inbox-no-llm.md, "
        "OPEN); no Skeptic, no MCP tools/list; tests: " + TESTS,
    ),
    "Liaison": (
        P,
        "core/agents/liaison.py: note as question, dismiss, snooze, drafts; no Slack sender, no "
        "learned-exception proposals, no LLM wording; tests: " + TESTS,
    ),
    "Owner memory": (
        P,
        "OwnerDecision written once per finding (core/agents/inbox_graph.py record_dismissal); the "
        "'same situation does not return without new evidence' rule is not built; tests: "
        "tests/integration/test_inbox_loop.py",
    ),
    "Show me why button": (
        D,
        "web inbox: api/inbox_actions.py show_why, ui/src/Thread.tsx; "
        + BROWSER
        + "; tests: "
        + TESTS,
    ),
    "Simulate a fix button": (
        P,
        "live simulate on GRAPH.COPY (core/agents/simulate_fix.py, core/hardening/xz.py); caught and "
        "lead time NOT COMPUTED (no saved red-team file); tests: tests/integration/test_inbox_loop.py",
    ),
    "Draft a reply button": (
        D,
        "core/agents/inbox_graph.py create_draft/edit_draft/mark_draft_sent; "
        + BROWSER
        + "; tests: "
        "tests/integration/test_inbox_loop.py",
    ),
    "Thread questions answered from tools": (
        D,
        "core/agents/investigator.py; " + BROWSER + "; tests: tests/unit/test_inbox_rules.py, "
        "tests/integration/test_inbox_loop.py",
    ),
    "Availability routing to the named backup": (
        D,
        "core/agents/routing.py (tested rules); api/inbox_actions.py routing endpoints; "
        "tests/unit/test_inbox_rules.py",
    ),
    "Weekly digest": (
        D,
        "core/agents/digest.py (saved results, quiet-week case); " + BROWSER + "; tests: "
        "tests/unit/test_inbox_rules.py",
    ),
    "Slack safety tests": (
        P,
        "injection and double-tap tests pass (tests/integration/test_inbox_loop.py); no Slack code "
        "exists in this build, so there is no Slack-down test",
    ),
    "Web inbox fallback": (
        D,
        "api/inbox_actions.py, ui/src/Thread.tsx mounted in ui/src/Inbox.tsx; "
        + BROWSER
        + "; tests: "
        + TESTS,
    ),
    "Inbox screen": (
        D,
        "ui/src/Inbox.tsx + ui/src/Thread.tsx: note, buttons and thread; " + BROWSER,
    ),
}
