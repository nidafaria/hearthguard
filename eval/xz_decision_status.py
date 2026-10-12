"""The decision policy on the real per-quarter detector statuses for org_xz.

Run: python -m eval.xz_decision_status
Reads two saved files, runs no query and no model:
  eval/results/pressure_vouch_status.json   (Pressure, Vouch)
  eval/results/xz_quarterly_status.json     (Rush, Bypass, Lone keeper)
Writes eval/results/decision_status.json: per quarter the four move statuses, the Lone keeper
status, the decision and its breakdown.

decide() is the frozen function and is called through decide_with_unknowns() (PROPOSED,
docs/decisions/0002): a move that is NOT_COMPUTED is "unknown", and if nothing else fires the
answer is HOLD("move unknown: ...") instead of NO_ACTION. No branch is added to decide().
"""

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from core.policy import decision as d

RESULTS = Path(__file__).resolve().parent / "results"
PV = RESULTS / "pressure_vouch_status.json"
QS = RESULTS / "xz_quarterly_status.json"
OUT = RESULTS / "decision_status.json"


def norm(status: str) -> str:
    return "NOT_COMPUTED" if status == "NOT COMPUTED" else status


def build() -> dict:
    pv = {q["quarter"]: q for q in json.loads(PV.read_text(encoding="utf-8"))["quarters"]}
    qs = {q["quarter"]: q for q in json.loads(QS.read_text(encoding="utf-8"))["quarters"]}
    rows = []
    for quarter in sorted(pv):
        moves = {
            "PRESSURE": norm(pv[quarter]["pressure"]["status"]),
            "VOUCH": norm(pv[quarter]["vouch"]["status"]),
            "RUSH": norm(qs[quarter]["checks"]["rush"]["status"]),
            "BYPASS": norm(qs[quarter]["checks"]["bypass"]["status"]),
        }
        lone = norm(qs[quarter]["checks"]["lone_keeper"]["status"])
        e = d.evidence_from_moves(
            moves, None, breakdown={"moves": moves, "lone_keeper": lone, "quarter": quarter}
        )
        result = d.decide_with_unknowns(e)
        rows.append(
            {
                "quarter": quarter,
                "T_iso": pv[quarter]["T_iso"],
                "moves": moves,
                "lone_keeper": lone,
                "reasons": {
                    "PRESSURE": pv[quarter]["pressure"]["reason"],
                    "VOUCH": pv[quarter]["vouch"]["reason"],
                    "RUSH": qs[quarter]["checks"]["rush"]["reason"],
                    "BYPASS": qs[quarter]["checks"]["bypass"]["reason"],
                },
                "decision": type(result).__name__,
                "detail": asdict(result),
            }
        )
    return {
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "policy": "decide() (frozen, spec 7.3) through decide_with_unknowns() (PROPOSED, "
        "docs/decisions/0002-decision-unknowns.md)",
        "inputs": [PV.name, QS.name],
        "provisional": True,
        "quarters": rows,
    }


def main() -> int:
    for p in (PV, QS):
        if not p.exists():
            print(f"{p.name} does not exist yet; run its script first")
            return 1
    doc = build()
    OUT.write_text(json.dumps(doc, indent=2, default=list) + "\n", encoding="utf-8")
    for r in doc["quarters"]:
        print(r["quarter"], r["decision"], r["detail"].get("reason", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
