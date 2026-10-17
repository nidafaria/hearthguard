#!/usr/bin/env python3
"""Manual verification script for Slack connectivity and listener readiness.

Usage:
    uv run python scripts/slack_check.py
    uv run python scripts/slack_check.py --listen --port 3000
    uv run python scripts/slack_check.py --channel C0123456789

Security & Policy Rules:
- Never prints SLACK_BOT_TOKEN or any secret key.
- Validates note phrasing (must end with question, no accusations).
- Uses Slack Web API over HTTPS.
"""

import argparse
from pathlib import Path
import sys

# Ensure repository root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from slack_app.client import (
    SenderNotConfigured,
    SlackDeliveryError,
    SlackSender,
    SlackWebClient,
    get_token,
)
from slack_app.listener import create_listener_app, start_listener


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify Slack bot credentials, listener startup, and optionally send a test note."
    )
    parser.add_argument(
        "--channel",
        "-c",
        help="Optional Slack channel or user ID (e.g. C0123456789 or U0123456789) to deliver a test note.",
        default=None,
    )
    parser.add_argument(
        "--listen",
        "-l",
        action="store_true",
        help="Start the live HTTP listener for Slack events and interactive actions.",
        default=False,
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        help="Port for the listener server (default: 3000).",
        default=3000,
    )
    parser.add_argument(
        "--host",
        help="Host for the listener server (default: 127.0.0.1).",
        default="127.0.0.1",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Hearthguard Slack Integration - Manual Check")
    print("=" * 60)

    # 1. Check token in environment
    try:
        token = get_token()
        print(f"[OK] SLACK_BOT_TOKEN detected in environment ({len(token)} characters).")
    except SenderNotConfigured as e:
        print(f"[ERROR] {e}")
        print("Please configure SLACK_BOT_TOKEN in your environment or .env file.")
        return 1

    # 2. Call auth.test
    client = SlackWebClient(token=token)
    try:
        auth_data = client.auth_test()
        print("[OK] Slack Web API authentication successful:")
        print(f"     Team / Workspace : {auth_data.get('team')} ({auth_data.get('team_id')})")
        print(f"     Bot User         : {auth_data.get('user')} ({auth_data.get('user_id')})")
        if auth_data.get("url"):
            print(f"     Workspace URL    : {auth_data.get('url')}")
    except SlackDeliveryError as e:
        print(f"[ERROR] Slack auth.test failed: {e}")
        return 2

    # 3. Confirm listener startup and health
    try:
        app = create_listener_app()
        test_client = TestClient(app)
        health_resp = test_client.get("/slack/health")
        if health_resp.status_code == 200 and health_resp.json().get("status") == "listening":
            print("[OK] Slack listener initialized and ready to receive events:")
            print(f"     Mode             : {health_resp.json().get('mode', 'events_api')}")
            print("     Endpoints        : /slack/actions, /slack/events, /slack/health")
        else:
            print(f"[ERROR] Listener health check returned unexpected: {health_resp.text}")
            return 3
    except Exception as e:
        print(f"[ERROR] Failed to initialize Slack listener: {e}")
        return 3

    # 4. Optional channel test send
    if args.channel:
        target_channel = args.channel.strip()
        print(f"\n[INFO] Sending test note to recipient: {target_channel}...")
        test_note_text = (
            "**Held: 2021-Q4** · public xz project history\n"
            "This is a test notification from Hearthguard.\n"
            "This is not a judgement about anyone.\n"
            "Would you like to review who can publish?"
        )
        sender = SlackSender(token=token, quarter="2021-Q4", case_id="xz")
        try:
            ts = sender.deliver(recipient_id=target_channel, text=test_note_text)
            print(f"[OK] Test note successfully delivered to {target_channel}!")
            print(f"     Message Timestamp (ts): {ts}")
        except Exception as e:
            print(f"[ERROR] Delivery failed: {e}")
            return 4
    else:
        print("\n[INFO] No --channel provided. Skipping test message delivery.")
        print("       To test sending a real note, run:")
        print("       uv run python scripts/slack_check.py --channel <CHANNEL_ID_OR_USER_ID>")

    # 5. Optional live listener execution
    if args.listen:
        print(f"\n[INFO] Starting live Slack listener on http://{args.host}:{args.port}...")
        print("       Press Ctrl+C to stop.")
        try:
            start_listener(host=args.host, port=args.port)
        except KeyboardInterrupt:
            print("\n[INFO] Listener stopped by user.")
    else:
        print("\n[INFO] To start the listener on a live port, run:")
        print(f"       uv run python scripts/slack_check.py --listen --port {args.port}")

    print("=" * 60)
    print("Check completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
