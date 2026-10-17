"""Unit tests for the Slack listener (Events API & Block Kit actions).

All network calls are mocked; no live Slack calls are made.
Tests verify:
- Inbound routing of button clicks for all 5 buttons (one click per button).
- Inbound routing of thread questions.
- Assertion that NO accusation is sent in any button reply or thread answer.
- Both application/json and application/x-www-form-urlencoded payloads.
- URL verification handshake and bot loop suppression.
- Listener health check endpoint.
"""

import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from slack_app.listener import create_listener_app, dispatch_slack_payload
from slack_app.rules import find_accusations


class MockHttpResponse:
    def __init__(self, status_code: int = 200, json_data: dict[str, Any] | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._json_data = json_data or {"ok": True, "ts": "1710000001.999999"}
        self.text = text or str(json_data)

    def json(self) -> dict[str, Any]:
        return self._json_data


class MockTransport:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> MockHttpResponse:
        self.requests.append({"method": method, "url": url, **kwargs})
        return MockHttpResponse(200, {"ok": True, "ts": "1710000001.999999"})


@pytest.fixture
def transport() -> MockTransport:
    return MockTransport()


@pytest.fixture
def client(transport: MockTransport) -> TestClient:
    app = create_listener_app(client_or_transport=transport)
    return TestClient(app)


def _build_action_payload(action_id: str, value: str = "xz:2021-Q4") -> dict[str, Any]:
    return {
        "type": "block_actions",
        "user": {"id": "U_OWNER_123"},
        "channel": {"id": "C_TEST_CHANNEL"},
        "message": {"ts": "1710000000.000100", "thread_ts": "1710000000.000100"},
        "actions": [
            {
                "action_id": action_id,
                "value": value,
                "type": "button",
            }
        ],
    }


# ----------------------------------------------------------------------------- 1. Button Clicks


def test_button_show_why_routes_and_sends_no_accusation(client: TestClient, transport: MockTransport) -> None:
    payload = _build_action_payload("action_show_why", "xz:2021-Q4")
    resp = client.post("/slack/actions", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["action"] == "action_show_why"
    assert "Show me why: 2021-Q4" in data["text"]

    # Verify no accusations sent
    assert find_accusations(data["text"]) == []

    # Verify outbound Slack request
    assert len(transport.requests) == 1
    outbound = transport.requests[0]["json"]
    assert outbound["channel"] == "C_TEST_CHANNEL"
    assert outbound["thread_ts"] == "1710000000.000100"
    assert find_accusations(outbound["text"]) == []


def test_button_simulate_fix_routes_and_sends_no_accusation(client: TestClient, transport: MockTransport) -> None:
    payload = _build_action_payload("action_simulate_fix", "xz:2021-Q4")
    resp = client.post("/slack/actions", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["action"] == "action_simulate_fix"
    assert "Simulate a fix for 2021-Q4" in data["text"]
    assert find_accusations(data["text"]) == []

    assert len(transport.requests) == 1
    outbound = transport.requests[0]["json"]
    assert find_accusations(outbound["text"]) == []


def test_button_draft_reply_routes_and_sends_no_accusation(client: TestClient, transport: MockTransport) -> None:
    payload = _build_action_payload("action_draft_reply", "xz:2021-Q4")
    resp = client.post("/slack/actions", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["action"] == "action_draft_reply"
    assert "Here is a drafted reply" in data["text"]
    assert find_accusations(data["text"]) == []

    assert len(transport.requests) == 1
    outbound = transport.requests[0]["json"]
    assert find_accusations(outbound["text"]) == []


def test_button_dismiss_routes_and_sends_no_accusation(client: TestClient, transport: MockTransport) -> None:
    payload = _build_action_payload("action_dismiss", "xz:2021-Q4")
    resp = client.post("/slack/actions", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["action"] == "action_dismiss"
    assert "marked as dismissed by owner" in data["text"]
    assert find_accusations(data["text"]) == []

    assert len(transport.requests) == 1
    outbound = transport.requests[0]["json"]
    assert find_accusations(outbound["text"]) == []


def test_button_snooze_routes_and_sends_no_accusation(client: TestClient, transport: MockTransport) -> None:
    payload = _build_action_payload("action_snooze", "xz:2021-Q4")
    resp = client.post("/slack/actions", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["action"] == "action_snooze"
    assert "snoozed for 7 days" in data["text"]
    assert find_accusations(data["text"]) == []

    assert len(transport.requests) == 1
    outbound = transport.requests[0]["json"]
    assert find_accusations(outbound["text"]) == []


# ----------------------------------------------------------------------------- 2. Thread Question


def test_thread_question_routes_and_sends_no_accusation(client: TestClient, transport: MockTransport) -> None:
    payload = {
        "type": "event_callback",
        "event": {
            "type": "message",
            "text": "Why was pressure unknown in 2021-Q4?",
            "channel": "C_TEST_CHANNEL",
            "thread_ts": "1710000000.000100",
            "user": "U_OWNER_123",
        },
    }
    resp = client.post("/slack/events", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["question"] == "Why was pressure unknown in 2021-Q4?"
    assert "answer" in data
    assert find_accusations(data["answer"]) == []

    # Verify outbound Slack post
    assert len(transport.requests) == 1
    outbound = transport.requests[0]["json"]
    assert outbound["channel"] == "C_TEST_CHANNEL"
    assert outbound["thread_ts"] == "1710000000.000100"
    assert find_accusations(outbound["text"]) == []


# ----------------------------------------------------------------------------- 3. Forms & Handshakes


def test_url_encoded_form_action_payload(client: TestClient, transport: MockTransport) -> None:
    raw_dict = _build_action_payload("action_show_why", "xz:2021-Q4")
    resp = client.post(
        "/slack/actions",
        data={"payload": json.dumps(raw_dict)},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["action"] == "action_show_why"
    assert len(transport.requests) == 1


def test_events_url_verification_handshake(client: TestClient) -> None:
    payload = {"type": "url_verification", "challenge": "hearthguard-challenge-test-123"}
    resp = client.post("/slack/events", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {"challenge": "hearthguard-challenge-test-123"}


def test_bot_message_ignored_to_prevent_loops(client: TestClient, transport: MockTransport) -> None:
    payload = {
        "type": "event_callback",
        "event": {
            "type": "message",
            "text": "Automatic bot message",
            "bot_id": "B_BOT_999",
            "channel": "C_TEST_CHANNEL",
        },
    }
    resp = client.post("/slack/events", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("ignored") == "bot_or_subtype_message"
    assert len(transport.requests) == 0


def test_listener_health_endpoint(client: TestClient) -> None:
    resp = client.get("/slack/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "listening", "mode": "events_api"}


def test_accusation_in_action_is_refused(transport: MockTransport) -> None:
    # If a malicious or buggy builder ever introduced an accusation, dispatcher refuses it
    bad_payload = _build_action_payload("action_show_why", "xz:2021-Q4")
    with pytest.raises(ValueError) as exc_info:
        with pytest.MonkeyPatch.context() as mp:
            from slack_app import client as slack_client
            mp.setattr(
                slack_client,
                "handle_slack_action",
                lambda **kwargs: {"ok": True, "text": "The maintainer is an attacker!"},
            )
            dispatch_slack_payload(bad_payload, client_or_transport=transport)
    assert "accusation detected in button reply" in str(exc_info.value)
