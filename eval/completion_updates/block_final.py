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
}
