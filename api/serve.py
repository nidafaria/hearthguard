"""Serve the local inbox: the API under /api and the built UI at /. Binds to 127.0.0.1 only.

Run: python -m api.serve   (make inbox builds the UI first, then runs this.)
Not connected to Slack. Nothing is sent.
"""

import uvicorn

from api.app import ROOT, create_app

HOST = "127.0.0.1"
PORT = 8765
app = create_app(static_dir=ROOT / "ui" / "dist")


def main() -> None:
    print(f"Inbox (local only, nothing sent): http://{HOST}:{PORT}/#/inbox")
    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
