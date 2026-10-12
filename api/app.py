"""Local inbox API for the note loop. Reads saved results, writes one local file, sends nothing.

Not connected to Slack. Every response carries a label saying what the data is: public record
or synthetic. The only write is a dismissal, appended to a local JSON Lines file.

Run through api/serve.py (make inbox). Tests build the app with create_app(...) on temp files.
"""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from api.inbox_actions import build_router
from slack_app.render import DECISION, render_note
from slack_app.show_why import RESULTS, facts_for, render_show_why

ROOT = Path(__file__).resolve().parent.parent
INBOX_FILE = ROOT / "data" / "inbox" / "dismissals.jsonl"
HARDENING_NAME = "xz_hardening.json"
LABEL = "Public record: xz project git history (org_xz). Synthetic data: none on this screen."
QUARTER_RE = re.compile(r"^\d{4}-Q[1-4]$")


class Dismissal(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


def create_app(
    results: Path = RESULTS,
    inbox_file: Path = INBOX_FILE,
    static_dir: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="Hearthguard inbox (local)")
    app.include_router(build_router(results, inbox_file))
    decision_file = results / DECISION.name
    hardening_file = results / HARDENING_NAME

    def load_rows() -> dict:
        doc = json.loads(decision_file.read_text(encoding="utf-8"))
        return {"doc": doc, "rows": {r["quarter"]: r for r in doc["quarters"]}}

    def row_or_404(quarter: str) -> dict:
        if not QUARTER_RE.match(quarter):
            raise HTTPException(404, "no such note")
        row = load_rows()["rows"].get(quarter)
        if row is None:
            raise HTTPException(404, "no such note")
        return row

    def read_dismissals() -> dict:
        found: dict = {}
        if not inbox_file.exists():
            return found
        for line in inbox_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                found.setdefault(rec["quarter"], rec)  # first dismissal wins: idempotent
        return found

    @app.get("/api/health")
    def health() -> dict:
        return {"label": LABEL, "sent_to_slack": False, "connected_to_slack": False}

    @app.get("/api/notes")
    def notes() -> dict:
        loaded = load_rows()
        dismissed = read_dismissals()
        items = []
        for row in loaded["doc"]["quarters"]:
            note = render_note(row)
            items.append(
                {
                    "quarter": row["quarter"],
                    "decision": row["decision"],
                    "headline": note.splitlines()[0],
                    "dismissed": row["quarter"] in dismissed,
                }
            )
        return {
            "label": LABEL,
            "provisional": loaded["doc"]["provisional"],
            "notes": items,
        }

    @app.get("/api/notes/{quarter}")
    def note(quarter: str) -> dict:
        row = row_or_404(quarter)
        return {
            "label": LABEL,
            "quarter": quarter,
            "decision": row["decision"],
            "note": render_note(row),
            "dismissal": read_dismissals().get(quarter),
        }

    @app.get("/api/notes/{quarter}/why")
    def why(quarter: str) -> dict:
        row = row_or_404(quarter)
        return {
            "label": LABEL,
            "quarter": quarter,
            "decision": row["decision"],
            "rule": row["detail"].get("breakdown", {}).get("rule", "not recorded"),
            "facts": facts_for(row, results),
            "text": render_show_why(row, results),
        }

    @app.get("/api/notes/{quarter}/simulate")
    def simulate(quarter: str) -> dict:
        row_or_404(quarter)
        base = {"label": LABEL, "quarter": quarter, "source": HARDENING_NAME}
        if not hardening_file.exists():
            return {
                **base,
                "available": False,
                "reason": (
                    f"{HARDENING_NAME} is not in eval/results yet, so no fix has been tested. "
                    "The hardening step (make harden) is not built yet."
                ),
                "result": None,
            }
        try:
            result = json.loads(hardening_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {
                **base,
                "available": False,
                "reason": f"{HARDENING_NAME} could not be read.",
                "result": None,
            }
        return {
            **base,
            "available": True,
            "reason": "Read from the saved file. This page computes nothing.",
            "result": result,
        }

    @app.post("/api/notes/{quarter}/dismiss")
    def dismiss(quarter: str, body: Dismissal) -> dict:
        row = row_or_404(quarter)
        reason = body.reason.strip()
        if len(reason) < 3:
            raise HTTPException(422, "a reason of at least 3 characters is required")
        existing = read_dismissals().get(quarter)
        if existing is not None:
            return {"label": LABEL, "already": True, "dismissal": existing}
        record = {
            "quarter": quarter,
            "decision": row["decision"],
            "reason": reason,
            "at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sent_to_slack": False,
        }
        inbox_file.parent.mkdir(parents=True, exist_ok=True)
        with inbox_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return {"label": LABEL, "already": False, "dismissal": record}

    if static_dir is not None and static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="ui")
    return app
