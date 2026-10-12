"""Hardening simulator on the real org_xz graph (docs/HEARTHGUARD.md section 8.5).

For each quarter-end and each step of the OSS menu: GRAPH.COPY org_<id> -> harden_<run>, apply the
step to the copy, and rerun takeover cost and guardians before (on the org graph, read only) and
after (on the copy). org_xz is never written to. Counts of org_xz are recorded before and after
the whole run so that is checkable from the file.

org_xz has no Privilege node and no grant edge (git has no grant record), so takeover cost and
guardians are NOT COMPUTED before and after. A step that finds nothing to change says so. No value
is filled in. The red-team half of 8.5 (caught, lead time) is not run here and not written.

Run: python -m core.hardening.xz   ->  eval/results/xz_hardening.json
"""

import json
import sys
import uuid
from pathlib import Path

from core.graph.client import FalkorClient
from core.hardening import simulate as sim
from core.takeover.scratch import RULE
from eval.xz_pressure_vouch_status import quarters

OUT = Path(__file__).resolve().parents[2] / "eval" / "results" / "xz_hardening.json"
ORG = "xz"


def _part(m: dict, kind: str) -> dict:
    """Status, value and reason for one of 'cost' or 'guardians' from sim.measure."""
    return {
        "status": m["cost_status"] if kind == "cost" else m["guardians_status"],
        "value": m[kind],
        "reason": m["cost_reason"] if kind == "cost" else None,
    }


def harden_org(
    client: FalkorClient, org: str, step: str, T: int, run: str | None = None
) -> dict:
    """One step on a copy of org_<org> at T. Before and after are measured, never filled in."""
    run = run or uuid.uuid4().hex[:10]  # a caller may pass its own run id (tests do)
    org_after = f"hza{run}"
    source, harden, evaluated = f"org_{org}", f"harden_{run}", f"org_{org_after}"
    try:
        for g in (harden, evaluated):
            client.drop(g)
        before = sim.measure(client, org, T)
        client.copy(source, harden)
        copy_counts = sim.counts(client, harden)
        changed = sim.apply_step(client, harden, step, T)
        client.copy(harden, evaluated)
        after = sim.measure(client, org_after, T)
    finally:
        for g in (harden, evaluated):
            client.drop(g)
    applied = any(v for v in changed.values())
    return {
        "step": step,
        "applied": applied,
        "graph_changes": changed,
        "copy_counts": copy_counts,
        "before": {"takeover_cost": _part(before, "cost"), "guardians": _part(before, "guardians")},
        "after": {"takeover_cost": _part(after, "cost"), "guardians": _part(after, "guardians")},
        "note": None
        if applied
        else "the step found nothing to change in this graph (no Privilege, grant edge or "
        "usual_path Normal to act on)",
    }


def build(client: FalkorClient, org: str = ORG) -> dict:
    org_before = sim.counts(client, f"org_{org}")
    rows = []
    for q in quarters():
        rows.append(
            {**q, "steps": [harden_org(client, org, s, q["T"]) for s in sim.MENU]},
        )
    return {
        "org": org,
        "privilege": sim.PRIV,
        "provisional": True,
        "rule": RULE,
        "spec": "docs/HEARTHGUARD.md section 8.5 (OSS menu: three rows)",
        "red_team": "not run: caught and lead time are not in this file",
        "org_counts_before": org_before,
        "org_counts_after": sim.counts(client, f"org_{org}"),
        "results": rows,
    }


def main() -> int:
    out = build(FalkorClient())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
