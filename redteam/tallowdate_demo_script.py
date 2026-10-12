"""The Hearthguard-side demo beats for tallowdate, as data (docs/HEARTHGUARD.md §3.5 Part 2).

Run: uv run python -m redteam.tallowdate_demo_script
Writes eval/results/tallowdate_demo_script.json. The beats are not world events, so they are not
in the generated history. Each beat names the saved file and field every number comes from. No
number is typed in here: a value is copied from that field when it exists, and is NOT COMPUTED
when it does not. Nothing is invented.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "eval" / "results"
SOURCE = ROOT / "data" / "synthetic" / "tallowdate.json"
OUT = RESULTS / "tallowdate_demo_script.json"
NOT_COMPUTED = "NOT COMPUTED"
LATEST = 11  # index of 2025-Q4 in tallowdate_detector_status.json quarters

LOAD = "eval/results/tallowdate_load.json"
DETECTORS = "eval/results/tallowdate_detector_status.json"
DECISION = "eval/results/tallowdate_decision.json"
NORMAL = "eval/results/tallowdate_normal.json"
EVENTS = "data/synthetic/tallowdate.json"


def _event_index(kind: str, actor: str | None = None, nth: int = 0) -> int:
    events = json.loads(SOURCE.read_text(encoding="utf-8"))["events"]
    hits = [
        i
        for i, e in enumerate(events)
        if e["kind"] == kind and (actor is None or e["actor"] == actor)
    ]
    return hits[nth]


def _beats() -> list[dict]:
    acct_a = _event_index("account_created", "acct-a")
    acct_b = _event_index("account_created", "acct-b")
    acct_c = _event_index("account_created", "acct-c")
    shipped = _event_index("release_signed", "Tomás")
    return [
        {
            "beat": "dm_note",
            "time": "Apr 2",
            "screen": "Slack DM to Mira",
            "text": "Four facts. Takeover cost: {cost}. One question.",
            "reads": {
                "cost": (DETECTORS, f"quarters.{LATEST}.checks.takeover_cost.status"),
            },
        },
        {
            "beat": "show_me_why",
            "time": "Apr 2",
            "screen": "Slack thread: Show me why",
            "text": (
                "Three accounts created on {created_a}, {created_b}, {created_c}. "
                "Never touched another project: {other_projects}."
            ),
            "reads": {
                "created_a": (EVENTS, f"events.{acct_a}.date"),
                "created_b": (EVENTS, f"events.{acct_b}.date"),
                "created_c": (EVENTS, f"events.{acct_c}.date"),
                "other_projects": (LOAD, "facts.other_project_touches.value"),
            },
        },
        {
            "beat": "simulate_fix",
            "time": "Apr 2",
            "screen": "Slack thread: Simulate a fix",
            "text": (
                "Second keeper and provenance: takeover cost {cost_before} -> {cost_after}. "
                "Planted attacks caught {caught_before} -> {caught_after}."
            ),
            "reads": {
                "cost_before": (DETECTORS, "hardening.takeover_cost_before"),
                "cost_after": (DETECTORS, "hardening.takeover_cost_after"),
                "caught_before": (DETECTORS, "hardening.caught_before"),
                "caught_after": (DETECTORS, "hardening.caught_after"),
            },
        },
        {
            "beat": "who_could_i_ask",
            "time": "Apr 2",
            "screen": "Slack thread: Who could I even ask?",
            "text": "Tomás has reviewed {reviews} of her pull requests over three years (generated).",
            "reads": {
                "reviews": (LOAD, "facts.tomas_review_count.value"),
            },
        },
        {
            "beat": "draft_reply",
            "time": "Apr 3",
            "screen": "Slack modal: Draft a reply to the pressure",
            "text": "Draft shown; Mira edits and posts it herself. Note state: {decision}.",
            "reads": {
                "decision": (DECISION, f"quarters.{LATEST}.decision"),
            },
        },
        {
            "beat": "dismiss_exception",
            "time": "Apr 3",
            "screen": "Slack thread: learned exception",
            "text": (
                "Exception tested against {planted} planted attacks, {lost} lost. "
                "Status: {status}."
            ),
            "reads": {
                "planted": (DECISION, "learning.planted_attacks_tested"),
                "lost": (DECISION, "learning.planted_attacks_lost"),
                "status": (DECISION, "learning.status"),
            },
        },
        {
            "beat": "tomas_accepts",
            "time": "Apr 10",
            "screen": "Weekly digest",
            "text": "Tomás accepts. Takeover cost: {cost}.",
            "reads": {
                "cost": (DETECTORS, f"quarters.{LATEST}.checks.takeover_cost.value"),
            },
        },
        {
            "beat": "rush_move",
            "time": "May 6",
            "screen": "Slack DM to both keepers",
            "text": "Rush move: {rush}.",
            "reads": {
                "rush": (DETECTORS, f"quarters.{LATEST}.checks.rush.status"),
            },
        },
        {
            "beat": "june_digest",
            "time": "June",
            "screen": "Weekly digest",
            "text": "Takeover cost {cost} · decision {decision} · {shipped}.",
            "reads": {
                "cost": (DETECTORS, f"quarters.{LATEST}.checks.takeover_cost.value"),
                "decision": (DECISION, f"quarters.{LATEST}.decision"),
                "shipped": (EVENTS, f"events.{shipped}.summary"),
            },
        },
    ]


def _resolve(path: str, field: str) -> tuple[bool, Any]:
    """Walk a dotted field path. Returns (found, value). Lists are indexed by integer."""
    node: Any = json.loads((ROOT / path).read_text(encoding="utf-8"))
    for part in field.split("."):
        try:
            node = node[int(part)] if isinstance(node, list) else node[part]
        except (KeyError, IndexError, ValueError, TypeError):
            return False, None
    if node is None:
        return False, None
    return True, node


def build_beat(beat: dict) -> dict:
    reads = {}
    values = {}
    for key, (path, field) in beat["reads"].items():
        found, value = _resolve(path, field)
        if not found:
            value = NOT_COMPUTED
        elif isinstance(value, str):
            value = value.rstrip(".")  # a saved sentence may end with a full stop of its own
        values[key] = value
        reads[key] = {
            "file": path,
            "field": field,
            "found": found,
            "value": values[key],
        }
    return {
        "beat": beat["beat"],
        "time": beat["time"],
        "screen": beat["screen"],
        "text": beat["text"].format(**values),
        "reads": reads,
        "synthetic": True,
    }


def build() -> dict:
    return {
        "synthetic": True,
        "case": "tallowdate",
        "label": "SYNTHETIC demo script. Beats are data, not claims.",
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "beats": [build_beat(b) for b in _beats()],
    }


def main() -> int:
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    for b in doc["beats"]:
        print(f"{b['time']:7s} {b['beat']}: {b['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
