"""Trust path (spec §7.6) from each tallowdate actor to the release privilege, per quarter-end.

Run: uv run python -m eval.trust_path_tallowdate
Reads org_tallowdate (load it first: make tallowdate-run).
Writes eval/results/trust_path_tallowdate.json.
Synthetic case: every actor is a fictional person or a hashed id. No grant record exists in it.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from core.graph.client import FalkorClient
from core.graph.hashing import identifier_hash
from core.takeover import trust_path as tp
from redteam.tallowdate_normal import QUARTER_ENDS, end_of_day_utc

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "eval" / "results" / "trust_path_tallowdate.json"
ORG = "tallowdate"
PRIVILEGE = "release"


def build(client: FalkorClient) -> dict:
    actors = {"Rowan (planted)": identifier_hash("Rowan"), "Tomás": identifier_hash("Tomás")}
    rows = []
    for quarter, d in QUARTER_ENDS:
        T = end_of_day_utc(d)
        per_actor = {}
        for label, hid in actors.items():
            r = tp.trust_path(client, ORG, hid, PRIVILEGE, T)
            per_actor[label] = {
                "status": r.status,
                "reason": r.reason,
                "weight": r.weight,
                "edges_read": r.edges_read,
                "query_ms": r.query_ms,
            }
        rows.append({"quarter": quarter, "T": T, "actors": per_actor})
    return {
        "synthetic": True,
        "case": ORG,
        "label": "SYNTHETIC: fictional project, fictional people",
        "privilege": PRIVILEGE,
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "NO PATH and NOT COMPUTED are results. The case records no grant, so a path to "
        "the release privilege is not expected.",
        "quarters": rows,
    }


def main() -> int:
    doc = build(FalkorClient())
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    for r in doc["quarters"]:
        print(r["quarter"], {k: v["status"] for k, v in r["actors"].items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
