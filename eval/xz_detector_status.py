"""Rush, Bypass and Lone keeper on the real org_xz graph: expected to be NOT_COMPUTED.

Run: python -m eval.xz_detector_status
Writes eval/results/xz_detector_status.json: per detector, the status, the reason and the queries
that showed it. It holds no computed value and no hashed id. The xz git ingest has no grant data
and records only `channel` and `verified` on a release path, so these detectors cannot judge it.
If a detector ever returns anything but NOT_COMPUTED here, this script stops with an error
instead of writing a result as a finding.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from core.detectors import bypass, lone_keeper, rush
from core.detectors.common import NOT_COMPUTED
from core.graph.as_of import run_as_of
from core.graph.client import FalkorClient

OUT = Path(__file__).resolve().parent / "results" / "xz_detector_status.json"
ORG = "xz"
PRIVILEGE = "release"
T = 1711929599  # 2024-03-31 23:59:59 UTC, as for the other xz status files
REDACTED = "<hashed id, not written>"

PICK_RELEASE = (
    "MATCH (a:Actor)-[d:DID]->(r:Action {kind: 'release'}) WHERE r.at <= $T "
    "RETURN r.ref AS ref, a.hid AS hid ORDER BY r.at DESC, r.ref DESC LIMIT 1"
)

SUFFIX = {
    "rush": " (git history has no grant record)",
    "lone_keeper": " (git history has no grant record)",
    "bypass": " (git records only channel and verified on a release path)",
}


def _redact(queries: list[dict]) -> list[dict]:
    out = []
    for q in queries:
        params = {k: (REDACTED if k in ("hid", "hids") else v) for k, v in q["params"].items()}
        out.append({**q, "params": params})
    return out


def build_status(client: FalkorClient) -> dict:
    row = run_as_of(client, f"org_{ORG}", PICK_RELEASE, {"T": T}).result_set
    if not row:
        raise RuntimeError("org_xz has no release action at T; run make ingest-xz first")
    action_ref, tagger = row[0]

    results = {
        "rush": rush.rush(client, ORG, PRIVILEGE, tagger, T),
        "bypass": bypass.bypass(client, ORG, action_ref, T),
        "lone_keeper": lone_keeper.lone_keeper(client, ORG, PRIVILEGE, T),
    }
    for name, res in results.items():
        if res.status != NOT_COMPUTED:
            raise RuntimeError(
                f"{name} on org_{ORG} is {res.status}: this file is only for the NOT_COMPUTED "
                "case, so nothing was written."
            )
    return {
        "org": ORG,
        "privilege": PRIVILEGE,
        "T": T,
        "T_iso": datetime.fromtimestamp(T, UTC).isoformat().replace("+00:00", "Z"),
        "action_ref": action_ref,
        "action_selection": "the most recent release at or before T, and its tagger for Rush",
        "provisional": True,
        "detectors": {
            name: {
                "status": res.status,
                "reason": res.reason + SUFFIX[name],
                "queries": _redact(res.queries),
            }
            for name, res in results.items()
        },
        "note": (
            "Not a finding. Real xz has no grant data and one shared release path, so none of "
            "the three detectors can be computed. The detectors are proven on hand-built graphs "
            "in tests/fixtures/detector_cases.py. Lone keeper depends on the PROPOSED takeover "
            "rule (docs/decisions/0001-outsider-edges.md)."
        ),
    }


def main() -> int:
    status = build_status(FalkorClient())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    for name, d in status["detectors"].items():
        print(f"{name:12s} {d['status']} - {d['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
