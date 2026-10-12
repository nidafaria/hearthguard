"""Liaison (spec 8.1, 12.2): the private note, the owner's replies, drafts and snooze.

Deterministic. No model is called (docs/decisions/0008-inbox-no-llm.md). The note is a question
with evidence behind it, never an accusation. The owner's reply is recorded as an OwnerDecision.
The code never contacts anyone: a draft is text the owner sends themselves.
"""

import json
import threading
from datetime import UTC, datetime
from pathlib import Path

from core.agents import inbox_graph as ig
from core.agents.cases import MOVES, Case, epoch
from core.graph.client import FalkorClient
from slack_app.render import LABEL, render_note
from slack_app.rules import ends_with_question, find_accusations

SNOOZE_DAYS = 7  # "Remind me in a week" (spec 12.2)
DAY_S = 86_400
BUTTON_LINE_START = "`[Show me why]`"

CONTROLS = (
    "Show me why",
    "Simulate a fix",
    "Draft a reply",
    "Dismiss with reason",
    "Remind me in a week",
)

DRAFT_KINDS = {
    "boundary_reply": (
        "Thanks for the interest in this. Releases ship when they're ready, and maintainership "
        "follows our documented process. I'll write back here if that changes."
    ),
    "invite_keeper": (
        "I'd like to share the release work so it does not rest on one person. Would you be "
        "willing to hold release rights alongside me, so that releases need two of us?"
    ),
}

_LOG_LOCK = threading.Lock()


def _alert_note(case: Case, row: dict) -> str:
    """The note for a NOTE decision (a move fired), in the shape of spec 12.2. A question, with
    the saved reason behind each fired move. Wording is checked like every other note."""
    fired = fired_moves(row)
    where = "synthetic demo data" if case.synthetic else "public record"
    lines = [
        f"**{len(fired)} facts about {case.org} match moves seen in past takeovers** "
        f"· {where} · as of {row['T_iso'][:10]}",
        "",
    ]
    for name in MOVES:
        status, reason = row["moves"][name], row["reasons"].get(name, "")
        label = LABEL[name]
        if status == "FIRED":
            lines.append(f"**{label}**: fired. {reason}".rstrip())
        elif status == "NOT_FIRED":
            lines.append(f"**{label}**: did not fire.")
        else:
            lines.append(f"**{label}**: unknown, not checked ({reason}).")
    lone = row["lone_keeper"]
    if lone == "FIRED":
        lines.append(f"**{LABEL['LONE_KEEPER']}**: you are the only person who can publish.")
    elif lone == "NOT_COMPUTED":
        lines.append(f"**{LABEL['LONE_KEEPER']}**: unknown, not checked.")
    lines += [
        "",
        "This is not a judgement about anyone. Would you like to review who can publish?",
    ]
    text = "\n".join(lines)
    found = find_accusations(text)
    if found or not ends_with_question(text):
        raise ValueError(f"{row['quarter']}: note wording rejected {found!r}")
    return text


def note_text(case: Case, row: dict) -> str:
    """The note as a question, without the Slack button line (the inbox has real buttons)."""
    if row["decision"] == "NOTE":
        return _alert_note(case, row)
    body = render_note(row)
    lines = [ln for ln in body.splitlines() if not ln.startswith(BUTTON_LINE_START)]
    text = "\n".join(lines).rstrip()
    if case.synthetic:
        text = text.replace("public xz project history", "synthetic demo data: tallowdate")
    return text


def headline(case: Case, row: dict) -> str:
    return note_text(case, row).splitlines()[0]


def fired_moves(row: dict) -> list[str]:
    names = [m for m, s in row["moves"].items() if s == "FIRED"]
    if row["lone_keeper"] == "FIRED":
        names.append("LONE_KEEPER")
    return sorted(names)


def snooze_status(
    snoozed_until: int | None, snoozed_moves: list[str] | None, fired_now: list[str], now: int
) -> dict:
    """The tested snooze rule (spec 12.2): a snoozed note comes back at the end of the week, or
    earlier only if a move fires that had not fired when it was snoozed."""
    if snoozed_until is None:
        return {"state": "active", "until": None, "new_moves": []}
    new = sorted(set(fired_now) - set(snoozed_moves or []))
    if new:
        return {"state": "raised_early", "until": snoozed_until, "new_moves": new}
    if now >= snoozed_until:
        return {"state": "due", "until": snoozed_until, "new_moves": []}
    return {"state": "snoozed", "until": snoozed_until, "new_moves": []}


def remind_in_a_week(client: FalkorClient, case: Case, row: dict, now: int) -> dict:
    until = now + SNOOZE_DAYS * DAY_S
    created = ig.snooze(client, case, row["quarter"], until, fired_moves(row), now)
    return {"already": not created}


def log_path(case: Case, base: Path) -> Path:
    """xz keeps the file block D reads. The synthetic case writes its own file, so a synthetic
    quarter that shares a name with an xz quarter never shows as an xz dismissal."""
    return base if case.id == "xz" else base.with_name(f"dismissals_{case.id}.jsonl")


def _read_log(path: Path, case: Case, quarter: str) -> dict | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec["quarter"] == quarter and rec.get("case", "xz") == case.id:
            return rec
    return None


def read_dismissal(case: Case, quarter: str, base: Path) -> dict | None:
    return _read_log(log_path(case, base), case, quarter)


def utc_iso(t: int) -> str:
    return datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def dismiss(
    client: FalkorClient, case: Case, row: dict, reason: str, now: int, base_log: Path
) -> dict:
    """Dismiss with a reason: one OwnerDecision (authority 'owner') and one log line, however
    many times the button is tapped. The first reason wins."""
    path = log_path(case, base_log)
    quarter = row["quarter"]
    earlier = _read_log(path, case, quarter)  # a line the older endpoint wrote still counts
    text = earlier["reason"] if earlier else reason
    at = epoch(earlier["at_utc"]) if earlier else now
    created = ig.record_dismissal(client, case, quarter, text, at)
    with _LOG_LOCK:
        record = _read_log(path, case, quarter)
        written = record is None
        if written:
            record = {
                "quarter": quarter,
                "decision": row["decision"],
                "reason": text,
                "at_utc": utc_iso(at),
                "sent_to_slack": False,
                "case": case.id,
                "action_key": f"dismiss:{case.id}:{quarter}",
                "authority": "owner",
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"already": not (created and written), "dismissal": record}


def draft_text(kind: str) -> str:
    if kind not in DRAFT_KINDS:
        raise KeyError(f"unknown draft kind {kind!r}; kinds are {sorted(DRAFT_KINDS)}")
    return DRAFT_KINDS[kind]
