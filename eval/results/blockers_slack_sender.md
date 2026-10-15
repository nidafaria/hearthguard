# Blocker: the real Slack sender (rows 22 and 100)

- Built: `slack_app/notify.py`, the send path against an injected `NoteSender` interface. It runs
  the action boundary and the wording rules, sends once per (case, quarter, recipient), and turns
  a sender failure into a `failed` result. Tested with a fake that records calls
  (`tests/unit/test_slack_notify.py`).
- Not built: the real sender. `UnimplementedSlackSender.deliver` raises `SenderNotImplemented`.
  Nothing is sent to anyone, no Bolt import, no network call, no token read.
- Needs a person: a Slack workspace, a bot token and the owner's Slack user id in `.env`.
- Unblock: implement `NoteSender.deliver` in `slack_app/send.py` (the one path named in
  `core/policy/boundary.py`), then update `tests/unit/test_boundary.py` expectations that today
  assert that file does not exist.
- Rows stay PARTIAL: 22 (Maintainer private note) and 100 (Slack app sends the note).
