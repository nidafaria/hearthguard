"""Unit tests for Slack Web API client, sender, and interactive handlers.

All network calls are mocked; no live Slack calls are made.
Tests verify:
- Token configuration and security invariants (token never leaked).
- Block Kit button construction.
- Web API client methods (auth.test, chat.postMessage).
- SlackSender delivery, accusation prevention, and question requirement.
- Interactive action handlers (Show why, Simulate fix, Draft reply, Dismiss, Snooze).
- Thread follow-up question handling.
- notify.py integration and fallback mechanisms.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from slack_app.client import (
    SenderNotConfigured,
    SlackDeliveryError,
    SlackSender,
    SlackWebClient,
    build_note_blocks,
    get_token,
    handle_slack_action,
    handle_slack_thread_question,
)
from slack_app.notify import SendLedger, UnimplementedSlackSender, get_default_sender, send_note


class MockHttpResponse:
    def __init__(self, status_code: int = 200, json_data: dict[str, Any] | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._json_data = json_data or {"ok": True}
        self.text = text or str(json_data)

    def json(self) -> dict[str, Any]:
        return self._json_data


class MockTransport:
    def __init__(self, response: MockHttpResponse | None = None) -> None:
        self.requests: list[dict[str, Any]] = []
        self.response = response or MockHttpResponse(200, {"ok": True, "ts": "1712345678.000100"})

    def request(self, method: str, url: str, **kwargs: Any) -> MockHttpResponse:
        self.requests.append({"method": method, "url": url, **kwargs})
        return self.response


VALID_NOTE = (
    "**Held: 2021-Q4** · public xz project history\n"
    "This is not a judgement about anyone.\n"
    "Would you like to review who can publish?"
)


# ----------------------------------------------------------------------------- Token and Config


def test_get_token_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token-12345")
    token = get_token()
    assert token == "xoxb-test-token-12345"


def test_get_token_missing_raises_sender_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    with pytest.raises(SenderNotConfigured) as exc_info:
        get_token()
    assert "SLACK_BOT_TOKEN is not set" in str(exc_info.value)
    # Ensure error does not leak anything sensitive
    assert "xoxb" not in str(exc_info.value)


# ----------------------------------------------------------------------------- Block Kit Builder


def test_build_note_blocks_structure() -> None:
    blocks = build_note_blocks("Hello note?", quarter="2021-Q4", case_id="xz")
    assert len(blocks) == 2
    assert blocks[0]["type"] == "section"
    assert blocks[0]["text"]["text"] == "Hello note?"

    actions = blocks[1]
    assert actions["type"] == "actions"
    buttons = actions["elements"]
    assert len(buttons) == 5

    action_ids = [btn["action_id"] for btn in buttons]
    assert action_ids == [
        "action_show_why",
        "action_simulate_fix",
        "action_draft_reply",
        "action_dismiss",
        "action_snooze",
    ]

    for btn in buttons:
        assert btn["value"] == "xz:2021-Q4"


# ----------------------------------------------------------------------------- SlackWebClient


def test_client_auth_test_success() -> None:
    transport = MockTransport(
        MockHttpResponse(200, {"ok": True, "team": "Hearthguard Lab", "user_id": "U12345", "bot_id": "B98765"})
    )
    client = SlackWebClient(token="mock-token", custom_transport=transport)
    res = client.auth_test()

    assert res["ok"] is True
    assert res["team"] == "Hearthguard Lab"
    assert len(transport.requests) == 1
    req = transport.requests[0]
    assert req["method"] == "POST"
    assert req["url"] == "https://slack.com/api/auth.test"
    assert req["headers"]["Authorization"] == "Bearer mock-token"


def test_client_post_chat_success() -> None:
    transport = MockTransport(MockHttpResponse(200, {"ok": True, "ts": "1234567.89"}))
    client = SlackWebClient(token="mock-token", custom_transport=transport)
    res = client.post_chat(
        channel="U-OWNER",
        text=VALID_NOTE,
        blocks=[{"type": "section"}],
        thread_ts="1234500.00",
    )

    assert res["ok"] is True
    assert res["ts"] == "1234567.89"
    assert len(transport.requests) == 1
    payload = transport.requests[0]["json"]
    assert payload["channel"] == "U-OWNER"
    assert payload["text"] == VALID_NOTE
    assert payload["blocks"] == [{"type": "section"}]
    assert payload["thread_ts"] == "1234500.00"


def test_client_http_error() -> None:
    transport = MockTransport(MockHttpResponse(500, text="Internal Server Error"))
    client = SlackWebClient(token="mock-token", custom_transport=transport)
    with pytest.raises(SlackDeliveryError) as exc_info:
        client.auth_test()
    assert "Slack HTTP error 500" in str(exc_info.value)


def test_client_api_error() -> None:
    transport = MockTransport(MockHttpResponse(200, {"ok": False, "error": "channel_not_found"}))
    client = SlackWebClient(token="mock-token", custom_transport=transport)
    with pytest.raises(SlackDeliveryError) as exc_info:
        client.post_chat(channel="C-BAD", text="Hello?")
    assert "Slack API error: channel_not_found" in str(exc_info.value)


# ----------------------------------------------------------------------------- SlackSender


def test_slack_sender_deliver_success() -> None:
    transport = MockTransport(MockHttpResponse(200, {"ok": True, "ts": "1710000000.123456"}))
    sender = SlackSender(token="test-token", custom_transport=transport, quarter="2021-Q4")
    ts = sender.deliver("U-OWNER", VALID_NOTE)

    assert ts == "1710000000.123456"
    assert len(transport.requests) == 1
    req = transport.requests[0]
    assert req["json"]["channel"] == "U-OWNER"
    assert req["json"]["blocks"] is not None


def test_slack_sender_deliver_refuses_accusation() -> None:
    transport = MockTransport()
    sender = SlackSender(token="test-token", custom_transport=transport)
    accusing_text = "The maintainer is an attacker! Would you like to review?"

    with pytest.raises(ValueError) as exc_info:
        sender.deliver("U-OWNER", accusing_text)
    assert "accusing wording" in str(exc_info.value)
    assert len(transport.requests) == 0


def test_slack_sender_deliver_refuses_note_without_question() -> None:
    transport = MockTransport()
    sender = SlackSender(token="test-token", custom_transport=transport)
    statement_only = "Held: 2021-Q4. Pressure fired."

    with pytest.raises(ValueError) as exc_info:
        sender.deliver("U-OWNER", statement_only)
    assert "note has no question line" in str(exc_info.value)
    assert len(transport.requests) == 0


def test_slack_sender_deliver_raises_on_missing_ts() -> None:
    transport = MockTransport(MockHttpResponse(200, {"ok": True}))  # ok True but no ts
    sender = SlackSender(token="test-token", custom_transport=transport)
    with pytest.raises(SlackDeliveryError) as exc_info:
        sender.deliver("U-OWNER", VALID_NOTE)
    assert "did not return a message timestamp" in str(exc_info.value)


# ----------------------------------------------------------------------------- Interactive Handlers


def test_handle_slack_action_show_why() -> None:
    transport = MockTransport(MockHttpResponse(200, {"ok": True, "ts": "1710000001.000000"}))
    custom_why = MagicMock(return_value="Show me why: verified facts here.")

    res = handle_slack_action(
        action_id="action_show_why",
        value="xz:2021-Q4",
        channel="C123",
        thread_ts="1710000000.000000",
        user_id="U123",
        client_or_transport=transport,
        why_builder=custom_why,
    )

    assert res["ok"] is True
    assert res["action"] == "action_show_why"
    assert res["case_id"] == "xz"
    assert res["quarter"] == "2021-Q4"
    assert res["reply_ts"] == "1710000001.000000"
    custom_why.assert_called_once_with("xz", "2021-Q4")
    assert len(transport.requests) == 1
    assert transport.requests[0]["json"]["thread_ts"] == "1710000000.000000"


def test_handle_slack_action_simulate_fix() -> None:
    transport = MockTransport(MockHttpResponse(200, {"ok": True, "ts": "1710000002.000000"}))
    res = handle_slack_action(
        action_id="action_simulate_fix",
        value="xz:2022-Q1",
        channel="C123",
        thread_ts="1710000000.000000",
        user_id="U123",
        client_or_transport=transport,
    )
    assert res["ok"] is True
    assert "Simulate a fix for 2022-Q1" in res["text"]
    assert "takeover cost" in res["text"]


def test_handle_slack_action_draft_reply() -> None:
    transport = MockTransport(MockHttpResponse(200, {"ok": True, "ts": "1710000003.000000"}))
    res = handle_slack_action(
        action_id="action_draft_reply",
        value="xz:2022-Q1",
        channel="C123",
        thread_ts="1710000000.000000",
        user_id="U123",
        client_or_transport=transport,
    )
    assert res["ok"] is True
    assert "Here is a drafted reply" in res["text"]
    assert "Hearthguard contacts no one" in res["text"]


def test_handle_slack_action_dismiss() -> None:
    transport = MockTransport(MockHttpResponse(200, {"ok": True, "ts": "1710000004.000000"}))
    dismiss_mock = MagicMock()
    res = handle_slack_action(
        action_id="action_dismiss",
        value="xz:2022-Q1",
        channel="C123",
        thread_ts="1710000000.000000",
        user_id="U123",
        client_or_transport=transport,
        dismiss_handler=dismiss_mock,
    )
    assert res["ok"] is True
    dismiss_mock.assert_called_once_with("xz", "2022-Q1", "Dismissed by owner via Slack action")
    assert "marked as dismissed by owner" in res["text"]


def test_handle_slack_action_snooze() -> None:
    transport = MockTransport(MockHttpResponse(200, {"ok": True, "ts": "1710000005.000000"}))
    snooze_mock = MagicMock()
    res = handle_slack_action(
        action_id="action_snooze",
        value="xz:2022-Q1",
        channel="C123",
        thread_ts="1710000000.000000",
        user_id="U123",
        client_or_transport=transport,
        snooze_handler=snooze_mock,
    )
    assert res["ok"] is True
    snooze_mock.assert_called_once_with("xz", "2022-Q1")
    assert "snoozed for 7 days" in res["text"]


def test_handle_slack_action_refuses_accusations() -> None:
    transport = MockTransport()
    bad_builder = MagicMock(return_value="The maintainer is an attacker.")
    with pytest.raises(ValueError) as exc_info:
        handle_slack_action(
            action_id="action_show_why",
            value="xz:2021-Q4",
            channel="C123",
            thread_ts="1710000000.000000",
            user_id="U123",
            client_or_transport=transport,
            why_builder=bad_builder,
        )
    assert "accusing wording" in str(exc_info.value)
    assert len(transport.requests) == 0


def test_handle_slack_thread_question() -> None:
    transport = MockTransport(MockHttpResponse(200, {"ok": True, "ts": "1710000006.000000"}))
    mock_inv = MagicMock(return_value="In 2021-Q4, pressure was unknown due to missing email data.")

    res = handle_slack_thread_question(
        question="Why did pressure fire?",
        channel="C123",
        thread_ts="1710000000.000000",
        user_id="U123",
        client_or_transport=transport,
        investigator_fn=mock_inv,
    )

    assert res["ok"] is True
    assert res["question"] == "Why did pressure fire?"
    assert res["answer"] == "In 2021-Q4, pressure was unknown due to missing email data."
    mock_inv.assert_called_once_with("Why did pressure fire?")
    assert len(transport.requests) == 1
    assert transport.requests[0]["json"]["text"] == res["answer"]
    assert transport.requests[0]["json"]["thread_ts"] == "1710000000.000000"


def test_handle_slack_thread_question_refuses_accusation() -> None:
    transport = MockTransport()
    mock_bad = MagicMock(return_value="Because they are the culprit!")
    with pytest.raises(ValueError) as exc_info:
        handle_slack_thread_question(
            question="Who did this?",
            channel="C123",
            thread_ts="1710000000.000000",
            user_id="U123",
            client_or_transport=transport,
            investigator_fn=mock_bad,
        )
    assert "accusing wording" in str(exc_info.value)
    assert len(transport.requests) == 0


# ----------------------------------------------------------------------------- Integration with notify.py


def test_get_default_sender_with_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-dummy-token")
    sender = get_default_sender()
    assert isinstance(sender, SlackSender)


def test_get_default_sender_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    sender = get_default_sender()
    assert isinstance(sender, UnimplementedSlackSender)


def test_send_note_with_slack_sender() -> None:
    transport = MockTransport(MockHttpResponse(200, {"ok": True, "ts": "1710000099.000000"}))
    sender = SlackSender(token="test-token", custom_transport=transport)
    ledger = SendLedger()

    res = send_note(
        sender,
        ledger,
        case_id="xz",
        quarter="2021-Q4",
        recipient="owner",
        recipient_id="U-OWNER",
        text=VALID_NOTE,
    )

    assert res.sent is True
    assert res.status == "sent"
    assert res.message_id == "1710000099.000000"
    assert len(transport.requests) == 1
