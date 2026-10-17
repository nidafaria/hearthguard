"""The send path for the private note (spec 4.3, 12.2), built against an injected sender.

`send_note` is the only way a note leaves the system. It runs the action boundary
(core/policy/boundary.py) and the wording rules (slack_app/rules.py) first, sends at most once
per (case, quarter, recipient), and never lets a sender failure reach the caller: the web inbox
works the same whether the sender is present, absent or broken.

The sender is an interface (`NoteSender`). Tests inject a fake that records calls. The real Slack
sender is deliberately not implemented: `UnimplementedSlackSender.deliver` raises, and the reason
is in eval/results/blockers_slack_sender.md. Nothing in this module opens a connection.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from core.policy import boundary
from slack_app.client import (
    SenderNotConfigured,
    SlackDeliveryError,
    SlackSender,
    SlackWebClient,
    build_note_blocks,
)
from slack_app.rules import ends_with_question, find_accusations

ACTION = "send_private_note"


class NoteSender(Protocol):
    """Delivers one private message. Returns a message id; raises on failure."""

    def deliver(self, recipient_id: str, text: str) -> str: ...


class SenderNotImplemented(NotImplementedError):
    """The real Slack sender is not built. See eval/results/blockers_slack_sender.md."""


class UnimplementedSlackSender:
    """Stands where the Slack sender will go. It never sends."""

    def deliver(self, recipient_id: str, text: str) -> str:
        raise SenderNotImplemented(
            "the real Slack sender is not implemented: needs a Slack workspace and bot token "
            "(eval/results/blockers_slack_sender.md)"
        )


def get_default_sender() -> NoteSender:
    """Returns real SlackSender if configured; falls back to UnimplementedSlackSender."""
    try:
        return SlackSender()
    except Exception:
        return UnimplementedSlackSender()


@dataclass(frozen=True)
class SendResult:
    status: str  # "sent" | "already_sent" | "refused" | "failed" | "no_sender"
    reason: str = ""
    message_id: str | None = None

    @property
    def sent(self) -> bool:
        return self.status == "sent"


class SendLedger:
    """Keys of notes already sent, so a double tap sends once. In memory; a caller may seed it."""

    def __init__(self, keys: set[str] | None = None) -> None:
        self.keys: set[str] = set(keys or ())

    def key(self, case_id: str, quarter: str, recipient: str) -> str:
        return f"send:{case_id}:{quarter}:{recipient}"


def send_note(
    sender: NoteSender | None,
    ledger: SendLedger,
    *,
    case_id: str,
    quarter: str,
    recipient: str,
    recipient_id: str,
    text: str,
    on_event: Callable[[str], None] | None = None,
) -> SendResult:
    """Send the note for one quarter to `recipient` ('owner' or 'backup') through `sender`.

    Refused, without calling the sender, when the boundary refuses the recipient, the text
    contains accusing wording, or the text has no question. A sender error is returned as
    status 'failed' and the note stays unsent, so a later tap can try again.
    """
    try:
        boundary.check(ACTION, recipient)
    except boundary.BoundaryViolation as e:
        return SendResult("refused", f"{e.rule}: {e}")
    found = find_accusations(text)
    if found:
        return SendResult("refused", f"accusing wording {found!r}")
    if not ends_with_question(text):
        return SendResult("refused", "note has no question line")
    if sender is None:
        return SendResult("no_sender", "no sender is configured; the note stays in the inbox")
    key = ledger.key(case_id, quarter, recipient)
    if key in ledger.keys:
        return SendResult("already_sent", key)
    try:
        message_id = sender.deliver(recipient_id, text)
    except Exception as e:  # any sender failure must leave the inbox working
        if on_event:
            on_event(f"send failed: {type(e).__name__}")
        return SendResult("failed", f"{type(e).__name__}: {e}")
    ledger.keys.add(key)
    return SendResult("sent", key, message_id)
