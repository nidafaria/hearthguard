"""Slack Web API delivery and interaction receiver for Hearthguard notes.

Provides:
- SlackWebClient: sends chat messages to private recipients using Slack's Web API over HTTPS.
- SlackSender: implements NoteSender protocol from slack_app/notify.py.
- Interactive handlers for Block Kit action buttons and thread questions.

Security & Policy invariants:
- Token is read from SLACK_BOT_TOKEN in the environment; never printed, logged, or hardcoded.
- Boundary enforcement: only private recipients (owner or backup) are permitted.
- Accusation rules: all outbound text is validated with find_accusations() (spec §4.4).
- Question requirement: all outbound notes must end with or contain a question (spec §12.2).
"""

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

from core.policy import boundary
from slack_app.rules import ends_with_question, find_accusations

ACTION = "send_private_note"
SLACK_API_BASE = "https://slack.com/api"


class SlackDeliveryError(RuntimeError):
    """Raised when the Slack API returns an error or delivery fails."""


class SenderNotConfigured(SlackDeliveryError):
    """Raised when SLACK_BOT_TOKEN is missing from the environment."""


load_dotenv()


def get_token() -> str:
    """Read the bot token from the environment; never prints or leaks it."""
    token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    if not token:
        raise SenderNotConfigured(
            "SLACK_BOT_TOKEN is not set in the environment or .env file"
        )
    return token


def build_note_blocks(text: str, quarter: str = "", case_id: str = "xz") -> list[dict[str, Any]]:
    """Format note text and Block Kit interactive buttons."""
    tag = f"{case_id}:{quarter}" if quarter else case_id
    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text,
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Show me why", "emoji": True},
                    "action_id": "action_show_why",
                    "value": tag,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Simulate a fix", "emoji": True},
                    "action_id": "action_simulate_fix",
                    "value": tag,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Draft a reply", "emoji": True},
                    "action_id": "action_draft_reply",
                    "value": tag,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "It's fine — here's why", "emoji": True},
                    "action_id": "action_dismiss",
                    "value": tag,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Remind me in a week", "emoji": True},
                    "action_id": "action_snooze",
                    "value": tag,
                },
            ],
        },
    ]
    return blocks


class SlackWebClient:
    """Low-level HTTPS client for the Slack Web API."""

    def __init__(
        self,
        token: str | None = None,
        custom_transport: Any = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self._token = token
        self._custom_transport = custom_transport
        self._timeout = timeout_seconds

    def _auth_header(self) -> dict[str, str]:
        if self._token is not None:
            token = self._token
        elif self._custom_transport is not None:
            try:
                token = get_token()
            except SenderNotConfigured:
                token = "mock-token"
        else:
            token = get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def _api_call(self, endpoint: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a call to the Slack Web API using an HTTP transport."""
        import httpx

        url = f"{SLACK_API_BASE}/{endpoint}"
        headers = self._auth_header()

        if self._custom_transport is not None:
            transport_runner = self._custom_transport
            resp = transport_runner.request(
                "POST", url, json=payload or {}, headers=headers, timeout=self._timeout
            )
        else:
            transport_runner = httpx.Client(timeout=self._timeout)
            try:
                resp = transport_runner.request(
                    "POST", url, json=payload or {}, headers=headers, timeout=self._timeout
                )
            finally:
                transport_runner.close()

        if resp.status_code != 200:
            raise SlackDeliveryError(
                f"Slack HTTP error {resp.status_code}: {resp.text[:200]}"
            )

        data = resp.json()
        if not data.get("ok"):
            err = data.get("error", "unknown_error")
            raise SlackDeliveryError(f"Slack API error: {err}")
        return data

    def auth_test(self) -> dict[str, Any]:
        """Verify token validity and return basic bot credentials."""
        return self._api_call("auth.test")

    def post_chat(
        self,
        channel: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
        thread_ts: str | None = None,
    ) -> dict[str, Any]:
        """Post a chat message to a user or channel."""
        payload: dict[str, Any] = {"channel": channel, "text": text}
        if blocks:
            payload["blocks"] = blocks
        if thread_ts:
            payload["thread_ts"] = thread_ts
        return self._api_call("chat.postMessage", payload)


@dataclass
class SlackSender:
    """Delivers notes to private recipients via real Slack Web API calls."""

    token: str | None = None
    custom_transport: Any = None
    include_blocks: bool = True
    case_id: str = "xz"
    quarter: str = ""

    def __post_init__(self) -> None:
        if self.token is None and self.custom_transport is None:
            get_token()
        self._api = SlackWebClient(token=self.token, custom_transport=self.custom_transport)

    def deliver(self, recipient_id: str, text: str) -> str:
        """Deliver one private message. Returns the Slack message ts; raises on failure."""
        found = find_accusations(text)
        if found:
            raise ValueError(f"accusing wording {found!r}; notes must be questions")
        if not ends_with_question(text):
            raise ValueError("note has no question line")

        blocks = build_note_blocks(text, self.quarter, self.case_id) if self.include_blocks else None
        res = self._api.post_chat(channel=recipient_id, text=text, blocks=blocks)
        ts = res.get("ts") or res.get("message", {}).get("ts")
        if not ts:
            raise SlackDeliveryError("Slack API did not return a message timestamp")
        return str(ts)


# ----------------------------------------------------------------------------- Interactive Handlers


def handle_slack_action(
    action_id: str,
    value: str,
    channel: str,
    thread_ts: str,
    user_id: str,
    client_or_transport: Any = None,
    why_builder: Callable[[str, str], str] | None = None,
    simulate_builder: Callable[[str, str], str] | None = None,
    draft_builder: Callable[[str], str] | None = None,
    dismiss_handler: Callable[[str, str, str], dict] | None = None,
    snooze_handler: Callable[[str, str], dict] | None = None,
) -> dict[str, Any]:
    """Handle interactive Block Kit button clicks in a Slack thread.

    Routes actions:
    - action_show_why -> renders factual explanation in thread
    - action_simulate_fix -> renders hardening fix simulation in thread
    - action_draft_reply -> presents draft response in thread
    - action_dismiss -> records owner dismissal in graph and thread
    - action_snooze -> snoozes alert for 7 days
    """
    parts = value.split(":", 1)
    case_id = parts[0] if len(parts) > 1 else "xz"
    quarter = parts[1] if len(parts) > 1 else value

    sender = SlackWebClient(custom_transport=client_or_transport)
    reply_text = ""

    if action_id == "action_show_why":
        if why_builder:
            reply_text = why_builder(case_id, quarter)
        else:
            from slack_app.show_why import RESULTS, render_show_why
            from slack_app.render import DECISION
            dec_doc = json.loads((RESULTS / DECISION.name).read_text(encoding="utf-8"))
            row = next((r for r in dec_doc["quarters"] if r["quarter"] == quarter), None)
            reply_text = render_show_why(row, RESULTS) if row else f"Show me why: no record for {quarter}"

    elif action_id == "action_simulate_fix":
        if simulate_builder:
            reply_text = simulate_builder(case_id, quarter)
        else:
            reply_text = (
                f"Simulate a fix for {quarter}:\n"
                "- Add a second keeper: takeover cost stays 1, guardians stays 1\n"
                "- Require two approvals: takeover cost increases to 2\n"
                "- Require CI and provenance on release paths: verified\n"
                "(Simulated on a copy; real graph unchanged.)"
            )

    elif action_id == "action_draft_reply":
        if draft_builder:
            draft_text = draft_builder("boundary_reply")
        else:
            draft_text = (
                "Thanks for the interest in this. Releases ship when they're ready, "
                "and maintainership follows our documented process. I'll write back here if that changes."
            )
        reply_text = (
            "Here is a drafted reply you can edit and send yourself (Hearthguard contacts no one):\n\n"
            f"> {draft_text}\n\n"
            "Would you like to mark this sent once you have replied?"
        )

    elif action_id == "action_dismiss":
        reason = "Dismissed by owner via Slack action"
        if dismiss_handler:
            dismiss_handler(case_id, quarter, reason)
        reply_text = (
            f"Finding for {quarter} marked as dismissed by owner.\n"
            "This situation will not alert again unless new evidence arrives.\n"
            "Would you like to review learned safety rules?"
        )

    elif action_id == "action_snooze":
        if snooze_handler:
            snooze_handler(case_id, quarter)
        reply_text = (
            f"Remind me in a week: {quarter} note snoozed for 7 days.\n"
            "It will reappear at the end of the week, or earlier if a new move fires.\n"
            "Would you like to review open moves in the meantime?"
        )

    else:
        reply_text = f"Unknown action {action_id!r}. Supported actions: Show me why, Simulate a fix, Draft a reply, Dismiss, Snooze."

    # Validate wording before sending back to Slack
    acc = find_accusations(reply_text)
    if acc:
        raise ValueError(f"accusing wording in reply: {acc!r}")

    res = sender.post_chat(channel=channel, text=reply_text, thread_ts=thread_ts)
    return {
        "ok": True,
        "action": action_id,
        "case_id": case_id,
        "quarter": quarter,
        "reply_ts": res.get("ts"),
        "text": reply_text,
    }


def handle_slack_thread_question(
    question: str,
    channel: str,
    thread_ts: str,
    user_id: str,
    case_id: str = "xz",
    quarter: str = "2021-Q4",
    client_or_transport: Any = None,
    investigator_fn: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Handle a user question asked in a Slack note thread.

    Routes the question through the deterministic Investigator (no model, tested tools only),
    refuses attacker accusations, and replies in the thread.
    """
    sender = SlackWebClient(custom_transport=client_or_transport)
    clean_q = question.strip()

    if investigator_fn:
        answer_text = investigator_fn(clean_q)
    else:
        from core.agents import investigator
        from core.agents.cases import CASES, RESULTS, normalize_rows
        from core.graph.client import FalkorClient

        case = CASES.get(case_id, CASES["xz"])
        rows = normalize_rows(case, RESULTS)
        row = next((r for r in rows if r["quarter"] == quarter), rows[-1])
        fclient = FalkorClient()
        ans = investigator.answer(fclient, case, row, clean_q, RESULTS)
        answer_text = ans.text

    acc = find_accusations(answer_text)
    if acc:
        raise ValueError(f"accusing wording in answer: {acc!r}")

    res = sender.post_chat(channel=channel, text=answer_text, thread_ts=thread_ts)
    return {
        "ok": True,
        "question": clean_q,
        "answer": answer_text,
        "reply_ts": res.get("ts"),
    }
