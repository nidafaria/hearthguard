"""Rush, Bypass, Lone keeper, takeover cost and guardians on org_xz at each quarter-end.

Run: python -m eval.xz_quarterly_status
Writes eval/results/xz_quarterly_status.json: per quarter and per check, the status, the reason
and the query time. These checks need no LLM. On real xz they are NOT_COMPUTED because the git
history holds no grant record and every release shares one Path node (see
eval/results/xz_detector_status.json). A value is never written as a finding: if any check
returns something other than NOT_COMPUTED, this script stops with an error instead.

Only checks that have an input at every quarter are run. Rush needs a grantee and Bypass needs a
release action, both taken as the latest release at or before the quarter-end, as in
eval/xz_detector_status.py. A quarter with no release before it records that and runs the checks
that need no release.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from core.detectors import bypass, lone_keeper, rush
from core.detectors.common import NOT_COMPUTED
from core.graph.as_of import run_as_of
from core.graph.client import FalkorClient
from core.takeover import cost, guardians
from eval import xz_detector_status as base
from eval.xz_pressure_vouch_status import quarters

OUT = Path(__file__).resolve().parent / "results" / "xz_quarterly_status.json"
ORG = "xz"
PRIVILEGE = "release"


def _check(res) -> dict:
    return {
        "status": res.status,
        "reason": res.reason,
        "query_ms": res.query_ms,
        "queries": base._redact(res.queries),
    }


def build(client: FalkorClient) -> dict:
    rows = []
    for q in quarters():
        T = q["T"]
        row = {**q, "checks": {}}
        pick = run_as_of(client, f"org_{ORG}", base.PICK_RELEASE, {"T": T}).result_set
        checks = {
            "takeover_cost": cost.takeover_cost(client, ORG, PRIVILEGE, T),
            "guardians": guardians.guardians(client, ORG, PRIVILEGE, T),
            "lone_keeper": lone_keeper.lone_keeper(client, ORG, PRIVILEGE, T),
        }
        if pick:
            ref, tagger = pick[0]
            row["latest_release_at_T"] = ref
            checks["rush"] = rush.rush(client, ORG, PRIVILEGE, tagger, T)
            checks["bypass"] = bypass.bypass(client, ORG, ref, T)
        else:
            row["latest_release_at_T"] = None
        for name, res in checks.items():
            if res.status not in (NOT_COMPUTED, cost.NOT_COMPUTED):
                raise RuntimeError(f"{name} at {q['quarter']} is {res.status}, not NOT_COMPUTED")
            row["checks"][name] = _check(res)
        if not pick:
            for name in ("rush", "bypass"):
                row["checks"][name] = {
                    "status": NOT_COMPUTED,
                    "reason": "no release action at or before this quarter-end",
                    "query_ms": None,
                    "queries": [],
                }
        rows.append(row)
    return {
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "org": ORG,
        "provisional": True,
        "quarters": rows,
    }


def main() -> int:
    doc = build(FalkorClient())
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.name}: {len(doc['quarters'])} quarters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
