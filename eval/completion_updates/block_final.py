# ruff: noqa: E501
"""Final-pass re-marks, applied last by eval/completion_full.py. Each entry names its evidence."""

D, P, N = "DONE", "PARTIAL", "NOT STARTED"

UPDATES = {
    "Maintainer private note": (
        P,
        "web inbox plus the send path: slack_app/notify.py sends through an injected NoteSender "
        "(boundary check, wording rules, once per note, failures contained) and is tested with a "
        "fake that records calls (tests/unit/test_slack_notify.py). The real Slack sender is not "
        "implemented and nothing is sent (eval/results/blockers_slack_sender.md).",
    ),
    "Slack app (Bolt, Socket Mode) sends the note": (
        P,
        "slack_app/render.py renders the note (eval/results/slack_preview.json, sent_to_slack "
        "false); slack_app/notify.py is the send path against a fake sender "
        "(tests/unit/test_slack_notify.py). No Bolt, no workspace, no token; nothing is sent "
        "(eval/results/blockers_slack_sender.md).",
    ),
    "Slack safety tests: injection, double tap, Slack down": (
        D,
        "injection and double-tap tests in tests/integration/test_inbox_loop.py; "
        "tests/integration/test_inbox_safety.py: no accusation in any note, draft or answer for "
        "both cases, one send per double tap, and the inbox unchanged with Slack down, "
        "unimplemented or absent (fake and failing senders; no real Slack).",
    ),
    "Patience curve": (
        D,
        "ui/src/Patience.tsx draws detection rate and lead time for full and forgetful memory "
        "from eval/results/ablation_memory.json (synthetic campaigns, labelled by the file); "
        "ui/src/Patience.test.tsx, ui/src/screens.test.tsx 'Patience'; vitest 40 passing, "
        "tsc --noEmit clean.",
    ),
    "Census screen": (
        P,
        "ui/src/Census.tsx at #/census: aggregate-only, NOT COMPUTED with the reason while "
        "eval/results/census.json is absent; ui/src/screens.test.tsx 'Census'. No census data "
        "exists (eval/results/blockers_census.md).",
    ),
    "Playbook screen": (
        D,
        "ui/src/Playbook.tsx and the #/playbook route; ui/src/screens.test.tsx 'Playbook' "
        "(exceptions with state and regression numbers, approve call, empty and error states); "
        "vitest 40 passing, tsc --noEmit clean. No browser check was run in this pass.",
    ),
}
