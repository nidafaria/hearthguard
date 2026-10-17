"""Slack Events and Interactivity listener for Hearthguard.

Receives inbound webhook events from Slack:
1. Interactive button clicks (Block Kit `block_actions`):
   - Dispatches to `slack_app.client.handle_slack_action()`
   - Routes `action_show_why`, `action_simulate_fix`, `action_draft_reply`, `action_dismiss`, `action_snooze`
2. Thread replies and questions (`event_callback` -> `message`):
   - Dispatches to `slack_app.client.handle_slack_thread_question()`
   - Routes user questions asked in Slack note threads to the Investigator
3. Handshake (`url_verification`):
   - Returns challenge for Slack Events API handshake

Security & Policy Rules:
- Uses bot token from environment only (never printed or leaked).
- Validates that replies contain NO accusations (`find_accusations`).
- Only replies in private threads to the requesting channel/user.
"""

import json
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from slack_app import client as slack_client
from slack_app.rules import find_accusations


def dispatch_slack_payload(
    payload: dict[str, Any],
    client_or_transport: Any = None,
) -> dict[str, Any]:
    """Parse and route any incoming Slack payload (block_actions, message event, or verification)."""
    p_type = payload.get("type")

    # 1. URL verification handshake
    if p_type == "url_verification":
        return {"challenge": payload.get("challenge", "")}

    # 2. Interactive Block Actions (Button clicks)
    if p_type == "block_actions":
        actions = payload.get("actions", [])
        if not actions:
            return {"ok": False, "error": "no_actions_in_payload"}

        first_action = actions[0]
        action_id = first_action.get("action_id", "")
        value = first_action.get("value", "")

        channel_id = (
            payload.get("channel", {}).get("id")
            or payload.get("container", {}).get("channel_id")
            or ""
        )
        thread_ts = (
            payload.get("message", {}).get("thread_ts")
            or payload.get("message", {}).get("ts")
            or payload.get("container", {}).get("message_ts")
            or ""
        )
        user_id = payload.get("user", {}).get("id", "")

        result = slack_client.handle_slack_action(
            action_id=action_id,
            value=value,
            channel=channel_id,
            thread_ts=thread_ts,
            user_id=user_id,
            client_or_transport=client_or_transport,
        )
        # Verify safety backstop
        acc = find_accusations(result.get("text", ""))
        if acc:
            raise ValueError(f"accusation detected in button reply: {acc!r}")
        return result

    # 3. Events API callbacks (Thread replies / messages)
    if p_type == "event_callback":
        event = payload.get("event", {})
        event_type = event.get("type")

        if event_type == "message":
            # Ignore bot messages and message edits to prevent infinite loops
            if event.get("bot_id") or event.get("subtype"):
                return {"ok": True, "ignored": "bot_or_subtype_message"}

            question = event.get("text", "").strip()
            channel_id = event.get("channel", "")
            thread_ts = event.get("thread_ts") or event.get("ts", "")
            user_id = event.get("user", "")

            result = slack_client.handle_slack_thread_question(
                question=question,
                channel=channel_id,
                thread_ts=thread_ts,
                user_id=user_id,
                client_or_transport=client_or_transport,
            )
            # Verify safety backstop
            acc = find_accusations(result.get("answer", ""))
            if acc:
                raise ValueError(f"accusation detected in thread answer: {acc!r}")
            return result

        return {"ok": False, "error": f"unhandled_event_type_{event_type}"}

    return {"ok": False, "error": f"unhandled_payload_type_{p_type}"}


def create_listener_app(client_or_transport: Any = None) -> FastAPI:
    """Create a FastAPI application configured as the Slack listener."""
    app = FastAPI(title="Hearthguard Slack Listener", version="0.1.0")

    @app.get("/slack/health")
    def health() -> dict[str, str]:
        return {"status": "listening", "mode": "events_api"}

    @app.post("/slack/actions")
    async def slack_actions(request: Request) -> Response:
        """Handle interactive component actions from Slack."""
        content_type = request.headers.get("content-type", "")
        if "application/x-www-form-urlencoded" in content_type:
            form = await request.form()
            raw_payload = form.get("payload")
            if not raw_payload:
                raise HTTPException(status_code=400, detail="Missing payload parameter")
            payload = json.loads(str(raw_payload))
        else:
            payload = await request.json()

        try:
            res = dispatch_slack_payload(payload, client_or_transport=client_or_transport)
            return JSONResponse(content=res)
        except ValueError as e:
            return JSONResponse(status_code=400, content={"ok": False, "error": str(e)})

    @app.post("/slack/events")
    async def slack_events(request: Request) -> Response:
        """Handle Slack Events API and dual-configured action webhooks."""
        content_type = request.headers.get("content-type", "")
        if "application/x-www-form-urlencoded" in content_type:
            form = await request.form()
            raw_payload = form.get("payload")
            if not raw_payload:
                raise HTTPException(status_code=400, detail="Missing payload parameter")
            payload = json.loads(str(raw_payload))
        else:
            payload = await request.json()

        # Handle URL verification challenge immediately
        if payload.get("type") == "url_verification":
            return JSONResponse(content={"challenge": payload.get("challenge", "")})

        try:
            res = dispatch_slack_payload(payload, client_or_transport=client_or_transport)
            return JSONResponse(content=res)
        except ValueError as e:
            return JSONResponse(status_code=400, content={"ok": False, "error": str(e)})

    return app


def start_listener(
    host: str = "127.0.0.1",
    port: int = 3000,
    client_or_transport: Any = None,
) -> None:
    """Start the Slack listener server."""
    import uvicorn

    app = create_listener_app(client_or_transport=client_or_transport)
    uvicorn.run(app, host=host, port=port)
