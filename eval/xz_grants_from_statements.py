"""Takeover cost and guardians on a COPY of org_xz loaded from public statements.

Run: python -m eval.xz_grants_from_statements
Writes data/derived/xz_grant_statements.json and eval/results/xz_grants_from_statements.json.
The real org_xz is never written. Not a system log; dates are approximate.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from core.graph.client import FalkorClient
from core.takeover import cost, guardians
from packs.oss import xz_statements as xs

ROOT = Path(__file__).resolve().parent.parent
STATEMENTS = ROOT / "data" / "derived" / "xz_grant_statements.json"
OUT = ROOT / "eval" / "results" / "xz_grants_from_statements.json"
SRC, COPY, ORG = "org_xz", "org_xz_statements", "xz_statements"
DAYS = ("2022-09-30", "2022-12-31", "2023-03-31", "2024-03-31")


def main() -> int:
    stmts = xs.build_statements()
    STATEMENTS.parent.mkdir(parents=True, exist_ok=True)
    STATEMENTS.write_text(
        json.dumps({"label": xs.LABEL, "statements": stmts}, indent=2) + "\n", encoding="utf-8"
    )
    client = FalkorClient()
    mapped = xs.load_into_copy(client, SRC, COPY, stmts)
    results = []
    for priv in ("release", "merge"):
        for day in DAYS:
            T = xs.unix_of(day) + 86399
            c = cost.takeover_cost(client, ORG, priv, T)
            g = guardians.guardians(client, ORG, priv, T)
            results.append(
                {
                    "privilege": priv,
                    "T": T,
                    "T_date": day,
                    "takeover_cost": {
                        "status": c.status,
                        "value": c.cost,
                        "reason": c.reason,
                        "path_length": len(c.path),
                    },
                    "guardians": {"status": g.status, "value": g.guardians, "reason": g.reason},
                }
            )
    doc = {
        "label": xs.LABEL,
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "graph_copied_from": SRC,
        "graph_written": COPY,
        "real_org_xz_written": False,
        "statements_total": len(stmts),
        "statements_as_edges": {"granted": len(mapped.granted), "can_grant": len(mapped.can_grant)},
        "rule": cost.sc.RULE,
        "provisional": True,
        "results": results,
    }
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(
        f"statements: {len(stmts)}; edges: {len(mapped.granted)} granted, "
        f"{len(mapped.can_grant)} can_grant"
    )
    for r in results:
        print(
            r["privilege"],
            r["T_date"],
            r["takeover_cost"]["status"],
            r["takeover_cost"]["value"],
            r["guardians"]["status"],
            r["guardians"]["value"],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
