"""The Slack note for each quarter, rendered from saved results only.

Run: python -m slack_app.render
Reads eval/results/decision_status.json and, for "Show me why", the two status files it names.
Writes eval/results/slack_preview.json: the note and the "Show me why" text for every quarter.
Nothing is sent. No Slack connection, no token, no model call.

The note is a question to the person in charge, never an accusation. A move that could not be
checked is shown as unknown, and a HOLD is shown as held.
"""

import json
from pathlib import Path

from slack_app.show_why import RESULTS, render_show_why

DECISION = RESULTS / "decision_status.json"
OUT = RESULTS / "slack_preview.json"

MOVES = ["PRESSURE", "VOUCH", "RUSH", "BYPASS"]
LABEL = {
    "PRESSURE": "Pressure",
    "VOUCH": "Vouch",
    "RUSH": "Rush",
    "BYPASS": "Bypass",
    "LONE_KEEPER": "Lone keeper",
}
STATUS_WORD = {"HOLD": "Held", "NO_ACTION": "No move fired"}
QUESTION = {
    "HOLD": "Would you like to add the records for the unknown moves, so they can be checked?",
    "NO_ACTION": "Would you like to keep watching this project?",
}
BUTTONS = (
    "`[Show me why]` `[Simulate a fix]` `[Draft a reply]` "
    "`[It's fine — here's why]` `[Remind me in a week]`"
)


def _move_line(name: str, status: str, reason: str) -> str:
    if status == "NOT_FIRED":
        return f"**{LABEL[name]}**: did not fire."
    if status == "FIRED":
        return f"**{LABEL[name]}**: fired."
    if status == "NOT_COMPUTED":
        return f"**{LABEL[name]}**: unknown, not checked ({reason})."
    raise ValueError(f"{name}: unexpected status {status!r}")


def _lone_keeper_line(status: str) -> str:
    if status == "NOT_FIRED":
        return f"**{LABEL['LONE_KEEPER']}**: did not fire."
    if status == "FIRED":
        return f"**{LABEL['LONE_KEEPER']}**: fired."
    if status == "NOT_COMPUTED":
        return f"**{LABEL['LONE_KEEPER']}**: unknown, not checked. See Show me why."
    raise ValueError(f"LONE_KEEPER: unexpected status {status!r}")


def render_note(row: dict) -> str:
    """The note for one quarter of decision_status.json. Uses only the fields in that file."""
    decision = row["decision"]
    if decision not in STATUS_WORD or decision not in QUESTION:
        raise ValueError(f"{row['quarter']}: no wording for decision {decision!r}")
    breakdown = row["detail"]["breakdown"]
    word = STATUS_WORD[decision]

    lines = [
        f"**{word}: {row['quarter']}** · public xz project history · as of {row['T_iso'][:10]}",
        "",
    ]
    for name in MOVES:
        lines.append(_move_line(name, row["moves"][name], row["reasons"][name]))
    lines.append(_lone_keeper_line(row["lone_keeper"]))
    lines.append("")

    unknown = list(breakdown.get("unknown_moves", []))
    if breakdown.get("lone_keeper_unknown"):
        unknown.append(LABEL["LONE_KEEPER"])
    if unknown:
        lines.append(
            f"Unknown: {', '.join(unknown)}. {word} means these were not checked, "
            "not that they are clear."
        )
    if "reason" in row["detail"]:
        lines.append(f"Why {word.lower()}: {row['detail']['reason']}.")
    lines.append("")
    lines.append(QUESTION[decision])
    lines.append("This is not a judgement about anyone.")
    lines.append(BUTTONS)
    return "\n".join(lines)


def build_preview(decision_doc: dict, results: Path = RESULTS) -> dict:
    """The preview file: a note and a Show me why text for every quarter, in order."""
    quarters = [
        {
            "quarter": row["quarter"],
            "decision": row["decision"],
            "note": render_note(row),
            "show_why": render_show_why(row, results),
        }
        for row in decision_doc["quarters"]
    ]
    return {
        "source": "public xz project history (org_xz)",
        "decision_status_generated_at_utc": decision_doc["generated_at_utc"],
        "provisional": decision_doc["provisional"],
        "sent_to_slack": False,
        "quarters": quarters,
    }


def main() -> int:
    decision_doc = json.loads(DECISION.read_text(encoding="utf-8"))
    preview = build_preview(decision_doc)
    OUT.write_text(json.dumps(preview, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.name}: {len(preview['quarters'])} quarters, none sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
