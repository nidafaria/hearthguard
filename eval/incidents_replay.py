"""Replay of a public incident on its org graph (spec §10.2 "Real cases"), shared by
eval/replay_event_stream.py and eval/replay_axios.py.

For each evaluation point T the frozen detectors run as of T (redteam/score.py judge(): Pressure,
Vouch, Rush, Bypass, Lone keeper, then decide_with_unknowns()), and takeover cost and guardians are
computed as of T. Nothing about a detector, policy or threshold is changed.

Definitions (also written into the output):
  e0                the time of the last release before the incident. Grants and releases AFTER
                    e0 and at or before T are what Rush and Bypass judge.
  evaluation points the times of the releases and grants after e0, up to and including the public
                    report (issue creation time), oldest first.
  first_fire        the first point whose decision is NOTE or WATCH; null if none.
  first_move_fired  the first point where any of the four moves is FIRED, whatever the decision.
  lead time         first_fire to the malicious release, and first_fire to the public report. Both
                    are null when nothing fired. Each is the difference of two recorded times.
Output carries no wall-clock time.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from core.detectors.common import FIRED
from core.graph.as_of import run_as_of
from core.graph.client import FalkorClient
from core.takeover import cost, guardians
from redteam import provenance, score

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "eval" / "results"
PRIV = "npm_publish"
DAY_S = 86_400

Q_RELEASES = (
    "MATCH (x:Action {kind: 'release'}) WHERE x.at > $e0 AND x.at <= $T "
    "RETURN x.at AS at ORDER BY at LIMIT 1000"
)
Q_GRANTS = (
    "MATCH ()-[g:GRANTED]->(:Privilege {kind: 'npm_publish'}) WHERE g.at > $e0 AND g.at <= $T "
    "RETURN g.at AS at ORDER BY at LIMIT 1000"
)

DEFINITIONS = {
    "e0": "time of the last release before the incident",
    "evaluation_points": "times of releases and grants after e0, up to the public report",
    "first_fire": "first point whose decision is NOTE or WATCH",
    "first_move_fired": "first point where any move is FIRED, whatever the decision; a decision "
    "other than NOTE or WATCH (for example HOLD) is not a note to the owner",
    "negative_lead_time": "a negative number of days means the first fire came AFTER that event",
    "lead_time": "first_fire to the malicious release, and to the public report; the difference "
    "of two recorded times; null when nothing fired",
}


def iso(t: int) -> str:
    return datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(root: Path, name: str):
    return json.loads((root / name).read_text(encoding="utf-8"))


def points(client: FalkorClient, graph: str, e0: int, report_at: int) -> list[int]:
    found = set()
    for q in (Q_RELEASES, Q_GRANTS):
        found |= {
            int(r[0]) for r in run_as_of(client, graph, q, {"e0": e0, "T": report_at}).result_set
        }
    return sorted(found)


def replay_graph(
    client: FalkorClient,
    org: str,
    e0: int,
    report_at: int,
    malicious_at: int,
    note_sources: list[str],
) -> dict:
    graph = f"org_{org}"
    rows = []
    first_fire = None
    first_move = None
    for t in points(client, graph, e0, report_at):
        pt = score.judge(client, org, PRIV, t, e0)
        c = cost.takeover_cost(client, org, PRIV, t)
        g = guardians.guardians(client, org, PRIV, t)
        if first_fire is None and pt.decision in score.CAUGHT_KINDS:
            first_fire = t
        if first_move is None and FIRED in pt.moves.values():
            first_move = t
        rows.append(
            {
                "T": t,
                "at_utc": iso(t),
                "moves": pt.moves,
                "lone_keeper": pt.lone_keeper,
                "decision": pt.decision,
                "decision_detail": pt.detail,
                "takeover_cost": {"status": c.status, "value": c.cost, "reason": c.reason},
                "guardians": {"status": g.status, "value": g.guardians, "reason": g.reason},
            }
        )
    fired = first_fire is not None
    return {
        "graph": graph,
        "points": rows,
        "fired": fired,
        "first_fire_utc": iso(first_fire) if fired else None,
        "lead_time_days_to_malicious_release": (
            round((malicious_at - first_fire) / DAY_S, 4) if fired else None
        ),
        "lead_time_days_to_public_report": (
            round((report_at - first_fire) / DAY_S, 4) if fired else None
        ),
        "first_move_fired_utc": iso(first_move) if first_move is not None else None,
        "first_move_fired_to_malicious_release_days": (
            round((malicious_at - first_move) / DAY_S, 4) if first_move is not None else None
        ),
        "bypass_fired_at": [r["at_utc"] for r in rows if r["moves"]["BYPASS"] == FIRED],
        "sources": note_sources,
    }


def envelope(
    case: str,
    e0: int,
    report_at: int,
    malicious_at: int,
    body: dict,
    notes: list[str] | None = None,
) -> dict:
    return {
        "case": case,
        "definitions": DEFINITIONS,
        "e0_utc": iso(e0),
        "public_report_utc": iso(report_at),
        "malicious_release_utc": iso(malicious_at),
        **body,
        "case_notes": notes or [],
        "honesty": [
            "One real incident per case is too few to claim precision (spec §10.2).",
            "Published as measured: a result that fired late, or not at all, is shown as it was.",
            "Rush: the registry records no grant event. A GRANTED edge is placed at the first "
            "version that lists the maintainer, which for a newcomer is also their first "
            "release, so days-to-grant is 0 by construction of the record. A Rush FIRED here is "
            "an effect of that record, not independent evidence.",
            "Lone keeper counts commit authors in the trailing 90 days; npm data has no commits, "
            "so only the guardians half of the flag can be set.",
        ],
        "provenance": provenance.provenance(),
    }


def write(doc: dict, name: str) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / name
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
