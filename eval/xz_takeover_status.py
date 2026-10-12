"""Takeover cost and guardians on the real org_xz graph: expected to be NOT COMPUTED.

Run: python -m eval.xz_takeover_status
Writes eval/results/xz_takeover_status.json. The xz git ingest wrote no Privilege nodes and no
grant edges (git has no grant record), so there is nothing to compute from. This file records
that status and the query that showed it. It never holds a cost or guardians value: if org_xz
ever gains grant data, this script stops with an error instead of writing a number as a finding.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from core.graph.client import FalkorClient
from core.takeover import cost, guardians
from core.takeover.scratch import RULE

OUT = Path(__file__).resolve().parent / "results" / "xz_takeover_status.json"
ORG = "xz"
PRIVILEGE = "release"
T = 1711929599  # 2024-03-31 23:59:59 UTC, the last quarter-end used for the xz normal metrics
GIT_REASON = "(git history has no grant record)"


def build_status(client: FalkorClient) -> dict:
    c = cost.takeover_cost(client, ORG, PRIVILEGE, T)
    g = guardians.guardians(client, ORG, PRIVILEGE, T)
    for name, res in (("takeover_cost", c), ("guardians", g)):
        if res.status != cost.NOT_COMPUTED:
            raise RuntimeError(
                f"{name} on org_{ORG} is {res.status}: grant data now exists. This file is only "
                "for the NOT COMPUTED case, so nothing was written."
            )

    def part(res) -> dict:
        return {
            "status": res.status,
            "value": None,
            "reason": f"{res.reason} {GIT_REASON}",
            "queries": res.queries,
        }

    return {
        "org": ORG,
        "privilege": PRIVILEGE,
        "T": T,
        "T_iso": datetime.fromtimestamp(T, UTC).isoformat().replace("+00:00", "Z"),
        "provisional": True,
        "rule": RULE,
        "takeover_cost": part(c),
        "guardians": part(g),
        "note": (
            "Not a finding. The xz git ingest has no Privilege nodes and no grant edges, so "
            "takeover cost and guardians cannot be computed on real xz data yet. The algorithms "
            "are proven on hand-built graphs in tests/fixtures/takeover_cases.py."
        ),
    }


def main() -> int:
    client = FalkorClient()
    status = build_status(client)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print(
        f"takeover_cost: {status['takeover_cost']['status']} - {status['takeover_cost']['reason']}"
    )
    print(f"guardians:     {status['guardians']['status']} - {status['guardians']['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
