"""The decision policy on the saved tallowdate statuses, per quarter-end.

Run: uv run python -m redteam.tallowdate_decision
Reads eval/results/tallowdate_detector_status.json only. Runs no query and no model.
Writes eval/results/tallowdate_decision.json. decide() is called through decide_with_unknowns()
as in eval/xz_decision_status.py. No branch is added to decide().

Pressure and Vouch are NOT COMPUTED here (reader not run), so every quarter's moves are unknown
and the answer is HOLD with the reason, not NO_ACTION.
"""

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from core.policy import decision as d

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "eval" / "results"
DETECTORS = RESULTS / "tallowdate_detector_status.json"
OUT = RESULTS / "tallowdate_decision.json"


def norm(status: str) -> str:
    return "NOT_COMPUTED" if status == "NOT COMPUTED" else status


def build() -> dict:
    src = json.loads(DETECTORS.read_text(encoding="utf-8"))
    rows = []
    for q in src["quarters"]:
        c = q["checks"]
        moves = {
            "PRESSURE": norm(c["pressure"]["status"]),
            "VOUCH": norm(c["vouch"]["status"]),
            "RUSH": norm(c["rush"]["status"]),
            "BYPASS": norm(c["bypass"]["status"]),
        }
        lone = norm(c["lone_keeper"]["status"])
        breakdown = {
            "moves": moves,
            "lone_keeper": lone,
            "takeover_cost": norm(c["takeover_cost"]["status"]),
            "guardians": norm(c["guardians"]["status"]),
            "quarter": q["quarter"],
        }
        e = d.evidence_from_moves(moves, None, breakdown=breakdown)
        result = d.decide_with_unknowns(e)
        rows.append(
            {
                "quarter": q["quarter"],
                "T": q["T"],
                "moves": moves,
                "lone_keeper": lone,
                "decision": type(result).__name__,
                "hold_reason": getattr(result, "reason", None),
                "detail": asdict(result),
                "inputs_from": {
                    "file": DETECTORS.name,
                    "quarter": q["quarter"],
                    "checks": ["pressure", "vouch", "rush", "bypass", "lone_keeper"],
                },
            }
        )
    return {
        "synthetic": True,
        "case": "tallowdate",
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "policy": "decide() (frozen, spec 7.3) through decide_with_unknowns() (PROPOSED, "
        "docs/decisions/0002-decision-unknowns.md)",
        "inputs": [DETECTORS.name],
        "provisional": True,
        "quarters": rows,
    }


def main() -> int:
    if not DETECTORS.exists():
        print(f"{DETECTORS.name} does not exist yet; run redteam.tallowdate_detectors first")
        return 1
    doc = build()
    OUT.write_text(
        json.dumps(doc, indent=2, default=list, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT}")
    for r in doc["quarters"]:
        print(r["quarter"], r["decision"], r["detail"].get("reason", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
