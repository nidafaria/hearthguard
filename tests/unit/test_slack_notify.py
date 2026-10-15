"""The send path with a fake sender: boundary, wording, one send per note, failures contained."""

import pytest

from slack_app import notify
from slack_app.notify import SenderNotImplemented, SendLedger, UnimplementedSlackSender, send_note

NOTE = (
    "Held: 2021-Q4.\nThis is not a judgement about anyone.\n"
    "Would you like to review who can publish?"
)


class FakeSender:
    def __init__(self, fail: Exception | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.fail = fail

    def deliver(self, recipient_id: str, text: str) -> str:
        self.calls.append((recipient_id, text))
        if self.fail:
            raise self.fail
        return f"msg-{len(self.calls)}"


def _send(sender, ledger, **kw):
    args = dict(
        case_id="xz", quarter="2021-Q4", recipient="owner", recipient_id="U-OWNER", text=NOTE
    )
    args.update(kw)
    return send_note(sender, ledger, **args)


def test_owner_note_is_sent_once_with_the_text_unchanged():
    s, ledger = FakeSender(), SendLedger()
    r = _send(s, ledger)
    assert r.sent and r.message_id == "msg-1"
    assert s.calls == [("U-OWNER", NOTE)]


def test_backup_may_receive_a_note():
    s = FakeSender()
    assert _send(s, SendLedger(), recipient="backup", recipient_id="U-BACKUP").sent


def test_double_tap_sends_once():
    s, ledger = FakeSender(), SendLedger()
    first, second = _send(s, ledger), _send(s, ledger)
    assert first.status == "sent" and second.status == "already_sent"
    assert len(s.calls) == 1


def test_a_different_quarter_or_recipient_is_a_different_send():
    s, ledger = FakeSender(), SendLedger()
    _send(s, ledger)
    _send(s, ledger, quarter="2022-Q1")
    _send(s, ledger, recipient="backup", recipient_id="U-B")
    assert len(s.calls) == 3


@pytest.mark.parametrize("recipient", ["flagged", "public", "channel", "", "OWNER"])
def test_a_recipient_who_is_not_private_is_refused_and_the_sender_is_not_called(recipient):
    s = FakeSender()
    r = _send(s, SendLedger(), recipient=recipient)
    assert r.status == "refused" and s.calls == []


@pytest.mark.parametrize(
    "text",
    [
        "This account is an attacker. Would you like to block it?",
        "He planted the change. Would you like to look?",
        "They are the culprit. Would you like to look?",
    ],
)
def test_accusing_wording_is_refused_and_the_sender_is_not_called(text):
    s = FakeSender()
    r = _send(s, SendLedger(), text=text)
    assert r.status == "refused" and "accusing" in r.reason and s.calls == []


def test_a_note_without_a_question_is_refused():
    s = FakeSender()
    r = _send(s, SendLedger(), text="Held: 2021-Q4. Nothing to ask.")
    assert r.status == "refused" and s.calls == []


def test_a_failing_sender_is_contained_and_a_retry_can_succeed():
    ledger = SendLedger()
    bad = FakeSender(fail=ConnectionError("slack down"))
    r = _send(bad, ledger)
    assert r.status == "failed" and "ConnectionError" in r.reason
    good = FakeSender()
    assert _send(good, ledger).sent  # the failure was not recorded as a send
    assert len(good.calls) == 1


def test_no_sender_leaves_the_note_unsent_without_error():
    r = _send(None, SendLedger())
    assert r.status == "no_sender" and not r.sent


def test_the_real_sender_is_unimplemented_and_sends_nothing():
    with pytest.raises(SenderNotImplemented):
        UnimplementedSlackSender().deliver("U-OWNER", NOTE)
    r = _send(UnimplementedSlackSender(), SendLedger())
    assert r.status == "failed" and "SenderNotImplemented" in r.reason


def test_the_module_opens_no_connection_and_reads_no_token():
    src = open(notify.__file__, encoding="utf-8").read()
    for word in (
        "import requests",
        "import httpx",
        "slack_sdk",
        "slack_bolt",
        "os.environ",
        "getenv",
    ):
        assert word not in src
