"""Hardening with a red-team test (docs/HEARTHGUARD.md section 8.5, 10.2): `make harden CASE=xz`.

For each step of the OSS menu (core/hardening/simulate.py MENU):
  1. GRAPH.COPY of the scaffolded case template to harden_<run>; the step is applied to that
     copy only.
  2. The SAME campaigns (generated from SEED and N, the same list as the baseline) are planted,
     one copy each, and the frozen detectors and decide_with_unknowns() score them.
  3. Takeover cost and guardians are measured on the step copy (org graph is never written).
The baseline is the same procedure with no step applied.

Definitions written into the output:
  takeover_cost, guardians   core/takeover, as of T = the end of the campaign horizon.
  caught                     NOTE or WATCH at any evaluation point of a campaign
                             (see redteam/run.py).
  median_lead_time_days      median of (final action day - first NOTE/WATCH day) over caught
                             campaigns.
  A step whose graph change touches nothing a detector or the cost reads is reported as
  "no change", not as a benefit: the provenance step writes Normal.provenance_required, which
  no frozen detector reads, so the test expects zero change there.

Writes eval/results/hardening_redteam_<case>.json. The real org graph is read only, and its
node and edge counts before and after are recorded in the output.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from core.graph.client import FalkorClient
from core.hardening import simulate as sim
from core.hardening.simulate import counts
from redteam import generate as gen
from redteam import plant, provenance, run, score

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "eval" / "results"
HORIZON_DAYS = plant.HORIZON_DAYS_AFTER_E0

DEFINITIONS = {
    "caught": run.DEFINITIONS["caught"],
    "lead_time_days": run.DEFINITIONS["lead_time_days"],
    "median_lead_time_days": "median of lead_time_days over caught campaigns; null if none caught",
    "takeover_cost_guardians_T": "as of the end of the campaign horizon on the copy",
    "no_change": "a step that touches nothing a frozen detector or the cost reads is reported as "
    "no change, not as a benefit",
}


def _label(case: str) -> str:
    return run.case_label(case)


def _lead_median(outcomes: list[score.Outcome]) -> float | None:
    leads = [o.lead_time_days for o in outcomes if o.lead_time_days is not None]
    return statistics.median(leads) if leads else None


def _measure_structure(client: FalkorClient, template: str, e0: int) -> dict:
    """Takeover cost and guardians on a copy of the template, as of the end of the horizon."""
    org = f"hm{uuid.uuid4().hex[:10]}"
    graph = f"org_{org}"
    T = e0 + HORIZON_DAYS * plant.DAY_S
    try:
        client.drop(graph)
        client.copy(template, graph)
        return sim.measure(client, org, T)
    finally:
        client.drop(graph)


def _scored(client: FalkorClient, template: str, camps: list[gen.Campaign], e0: int) -> dict:
    outs = run.evaluate(client, template, camps, e0)
    s = score.summarise(outs)
    return {
        "n": s["n"],
        "caught": s["caught"],
        "missed": s["missed"],
        "caught_rate": s["detection_rate"],
        "median_lead_time_days": _lead_median(outs),
    }


def run_hardening(case: str, n: int, seed: int, client: FalkorClient | None = None) -> dict:
    client = client or FalkorClient()
    camps = gen.generate(n, seed, case)
    base_run = run.new_run_id()
    info = run.make_template(client, case, base_run)
    template, e0 = info["template"], info["e0"]
    rows = []
    try:
        baseline_struct = _measure_structure(client, template, e0)
        baseline = _scored(client, template, camps, e0)
        for step in sim.MENU:
            step_run = run.new_run_id()
            hardened = f"harden_{step_run}"
            try:
                client.drop(hardened)
                client.copy(template, hardened)
                changed = sim.apply_step(client, hardened, step, e0)
                struct = _measure_structure(client, hardened, e0)
                after = _scored(client, hardened, camps, e0)
            finally:
                client.drop(hardened)
            rows.append(
                {
                    "step": step,
                    "graph_changes": changed,
                    "changed_anything": any(bool(v) for v in changed.values()),
                    "takeover_cost": {
                        "before": baseline_struct["cost"],
                        "after": struct["cost"],
                        "before_status": baseline_struct["cost_status"],
                        "after_status": struct["cost_status"],
                    },
                    "guardians": {
                        "before": baseline_struct["guardians"],
                        "after": struct["guardians"],
                        "before_status": baseline_struct["guardians_status"],
                        "after_status": struct["guardians_status"],
                    },
                    "campaigns": {"before": baseline, "after": after},
                }
            )
    finally:
        client.drop(template)
    return {
        "case": case,
        "label": _label(case),
        "n": n,
        "seed": seed,
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "definitions": DEFINITIONS,
        "menu": list(sim.MENU),
        "campaigns_sha256": run.campaigns_sha256(camps),
        "e0": e0,
        "baseline_campaigns": baseline,
        "steps": rows,
        "provenance": provenance.provenance(),
        "note": "the template holds the same scaffold for before and after; only the menu step "
        "differs between them",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="tallowdate", choices=gen.CASES)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args(argv)
    client = FalkorClient()
    real = f"org_{a.case}"
    real_before = counts(client, real)
    doc = run_hardening(a.case, a.n, a.seed, client)
    real_after = counts(client, real)
    doc["real_graph"] = {
        "name": real,
        "port": client.port,
        "counts_before": real_before,
        "counts_after": real_after,
        "unchanged": real_before == real_after,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"hardening_redteam_{a.case}.json"
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path}")
    print(f"real graph unchanged: {doc['real_graph']['unchanged']}")
    for r in doc["steps"]:
        b, a2 = r["campaigns"]["before"], r["campaigns"]["after"]
        print(
            f"{r['step']:<24} caught {b['caught']}->{a2['caught']} of {b['n']}  "
            f"cost {r['takeover_cost']['before']}->{r['takeover_cost']['after']}  "
            f"guardians {r['guardians']['before']}->{r['guardians']['after']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
