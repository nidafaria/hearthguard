"""Rush, Bypass, Lone keeper, takeover cost and guardians on org_tallowdate, per quarter-end.

Run: uv run python -m redteam.tallowdate_detectors
Writes eval/results/tallowdate_detector_status.json: per quarter and per check the status, the
reason, the query and its time. The same functions as eval/xz_quarterly_status.py, unchanged.
Privilege is "release". Pressure and Vouch are not run here (no reader run on this case).

Function hashes: the source of each detector function is hashed here and compared with the same
function at the commit that last wrote eval/results/xz_detector_status.json. A mismatch is
recorded in the file and fails the integration test.
"""

import ast
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from core.detectors import bypass, lone_keeper, rush
from core.graph.as_of import run_as_of
from core.graph.client import FalkorClient
from core.takeover import cost, guardians
from eval import xz_detector_status as base
from redteam.load_tallowdate import ORG_ID
from redteam.tallowdate_normal import QUARTER_ENDS, end_of_day_utc

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "eval" / "results" / "tallowdate_detector_status.json"
PRIVILEGE = "release"
NOT_RUN = "NOT COMPUTED"
PV_REASON = "reader not run on synthetic case in this step"

# (module path, function name) for each check, as they appear in the repo.
FUNCTIONS = {
    "rush": ("core/detectors/rush.py", "rush"),
    "bypass": ("core/detectors/bypass.py", "bypass"),
    "lone_keeper": ("core/detectors/lone_keeper.py", "lone_keeper"),
    "takeover_cost": ("core/takeover/cost.py", "takeover_cost"),
    "guardians": ("core/takeover/guardians.py", "guardians"),
}


def _function_source(text: str, name: str) -> str:
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            segment = ast.get_source_segment(text, node)
            if segment is None:
                raise ValueError(f"no source for {name}")
            return segment
    raise ValueError(f"function {name} not found")


def _git(*args: str) -> str:
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def function_hashes() -> dict[str, dict]:
    ref_commit = _git("log", "-1", "--format=%H", "--", "eval/results/xz_detector_status.json")
    out: dict[str, dict] = {}
    for check, (path, name) in FUNCTIONS.items():
        current = _function_source((ROOT / path).read_text(encoding="utf-8"), name)
        reference = _function_source(_git("show", f"{ref_commit}:{path}"), name)
        cur_hash = hashlib.sha256(current.encode("utf-8")).hexdigest()
        ref_hash = hashlib.sha256(reference.encode("utf-8")).hexdigest()
        out[check] = {
            "file": path,
            "function": name,
            "sha256": cur_hash,
            "xz_reference_sha256": ref_hash,
            "xz_reference_commit": ref_commit,
            "match": cur_hash == ref_hash,
        }
    return out


def _check(res) -> dict:
    return {
        "status": res.status,
        "reason": res.reason,
        "query_ms": res.query_ms,
        "queries": base._redact(res.queries),
    }


def build(client: FalkorClient) -> dict:
    rows = []
    for quarter, d in QUARTER_ENDS:
        T = end_of_day_utc(d)
        pick = run_as_of(client, f"org_{ORG_ID}", base.PICK_RELEASE, {"T": T}).result_set
        checks = {
            "takeover_cost": cost.takeover_cost(client, ORG_ID, PRIVILEGE, T),
            "guardians": guardians.guardians(client, ORG_ID, PRIVILEGE, T),
            "lone_keeper": lone_keeper.lone_keeper(client, ORG_ID, PRIVILEGE, T),
        }
        row = {
            "quarter": quarter,
            "T": T,
            "latest_release_at_T": pick[0][0] if pick else None,
            "checks": {},
        }
        if pick:
            ref, tagger = pick[0]
            checks["rush"] = rush.rush(client, ORG_ID, PRIVILEGE, tagger, T)
            checks["bypass"] = bypass.bypass(client, ORG_ID, ref, T)
        for name, res in checks.items():
            row["checks"][name] = _check(res)
        if not pick:
            for name in ("rush", "bypass"):
                row["checks"][name] = {
                    "status": NOT_RUN,
                    "reason": "no release action at or before this quarter-end",
                    "query_ms": None,
                    "queries": [],
                }
        row["checks"]["pressure"] = {"status": NOT_RUN, "reason": PV_REASON, "queries": []}
        row["checks"]["vouch"] = {"status": NOT_RUN, "reason": PV_REASON, "queries": []}
        rows.append(row)
    return {
        "synthetic": True,
        "case": "tallowdate",
        "org": ORG_ID,
        "privilege": PRIVILEGE,
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "provisional": True,
        "note": (
            "Synthetic case, not a finding. The generated events record no grant, so Rush, "
            "Lone keeper, takeover cost and guardians have nothing to read. A status other than "
            "NOT COMPUTED would be recorded here as it is, and no branch in the policy handles it."
        ),
        "function_hashes": function_hashes(),
        "quarters": rows,
    }


def main() -> int:
    doc = build(FalkorClient())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    for r in doc["quarters"]:
        s = {k: v["status"] for k, v in r["checks"].items()}
        print(r["quarter"], s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
