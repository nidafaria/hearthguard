"""`make redteam N=200 SEED=7 CASE=tallowdate`: plant N campaigns into copies, score the frozen
detectors, write eval/results/redteam_<case>.json (spec 6.3, 8.1, 10.3).

Graphs made (all dropped before the run ends):
  redteam_<run>      GRAPH.COPY of org_<case>, plus the scaffold (redteam/plant.py).
  org_rt<run>c<i>    GRAPH.COPY of redteam_<run> per campaign, with that one campaign planted. The
                     detectors read graphs named org_<id>, and a separate copy per campaign keeps
                     one campaign's grants out of another's Rush history.
The real org graph is only read: GRAPH.COPY, then node and edge counts before and after.

Every campaign result carries no hashed id. The file carries the git commit and the hash of each
frozen detector function (redteam/provenance.py).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from core.graph.client import FalkorClient
from core.hardening.simulate import counts
from redteam import generate as gen
from redteam import plant, provenance, score

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "eval" / "results"

DEFINITIONS = {
    "caught": "NOTE or WATCH from decide_with_unknowns() at any evaluation point, i.e. by the "
    "campaign's last move",
    "evaluation_points": "the times of the campaign's own moves; the frozen detectors run as of "
    "each one on the planted copy",
    "lead_time_days": "days from the first evaluation point whose decision is NOTE or WATCH to the "
    "final action; the final action is the Bypass release if the campaign has one, else its last "
    "move; undefined for a missed campaign",
    "detection_rate": "caught / N",
    "scaffold": "synthetic benign structure planted into the copy because neither public graph "
    "records a grant or a release path; parameters are in redteam/generate.py and are not data "
    "about any project",
}


# Node and edge counts of the real graphs as saved by the build (xz: with the Reader claims written;
# tallowdate: with its Normal nodes). A run records whether the graph it ran on equals these.
SAVED_BASELINES = {"xz": {"nodes": 4679, "edges": 4668}, "tallowdate": {"nodes": 175, "edges": 168}}


def baseline_check(case: str, found: dict) -> dict:
    saved = SAVED_BASELINES[case]
    got = {"nodes": found["nodes"], "edges": found["edges"]}
    return {"saved_baseline": saved, "found": got, "matches_saved_baseline": got == saved}


def case_label(case: str) -> str:
    if case == "xz":
        return (
            "campaign planted into a copy of public xz history; not a finding about xz; "
            "run on an isolated rebuild of org_xz, 4669 nodes / 4659 edges; "
            "saved baseline 4679 / 4668"
        )
    return "SYNTHETIC: campaign planted into a copy of the fictional tallowdate history"


def new_run_id() -> str:
    return uuid.uuid4().hex[:10]


def make_template(
    client: FalkorClient,
    case: str,
    run: str,
    *,
    prefix: str = "redteam",
    keepers: int = 1,
) -> dict:
    """GRAPH.COPY org_<case> -> <prefix>_<run>, then plant the scaffold into the copy."""
    base, template = f"org_{case}", f"{prefix}_{run}"
    before = counts(client, base)
    client.drop(template)
    client.copy(base, template)
    e0 = plant.epoch(client, template)
    scaffold_id = f"scaffold-{case}"
    sc = plant.plant_scaffold(client, template, scaffold_id, e0, keepers=keepers)
    return {
        "base": base,
        "template": template,
        "e0": e0,
        "day0": plant.day0(e0),
        "scaffold": sc,
        "real_counts_before": before,
    }


def evaluate(
    client: FalkorClient,
    template: str,
    camps: list[gen.Campaign],
    e0: int,
    *,
    memory_window_days: int | None = None,
) -> list[score.Outcome]:
    """Plant each campaign into its own copy of `template`, score it, drop the copy."""
    day0 = plant.day0(e0)
    out = []
    for camp in camps:
        org = f"rt{new_run_id()}"
        graph = f"org_{org}"
        try:
            client.drop(graph)
            client.copy(template, graph)
            resolved = plant.plant_campaign(client, graph, camp, day0)
            out.append(
                score.score_campaign(
                    client, org, camp, resolved, e0, memory_window_days=memory_window_days
                )
            )
        finally:
            client.drop(graph)
    return out


def by_patience(outcomes: list[score.Outcome]) -> list[dict]:
    groups: dict[int, list[score.Outcome]] = defaultdict(list)
    for o in outcomes:
        groups[o.patience_days].append(o)
    return [{"patience_days": p, **score.summarise(groups[p])} for p in sorted(groups)]


def by_moves(outcomes: list[score.Outcome]) -> list[dict]:
    groups: dict[str, list[score.Outcome]] = defaultdict(list)
    for o in outcomes:
        groups["+".join(o.moves) or "none"].append(o)
    return [{"moves": m, **score.summarise(groups[m])} for m in sorted(groups)]


def campaigns_sha256(camps: list[gen.Campaign]) -> str:
    return hashlib.sha256(gen.to_bytes(camps)).hexdigest()


def run_redteam(case: str, n: int, seed: int, client: FalkorClient | None = None) -> dict:
    client = client or FalkorClient()
    start = time.perf_counter()
    camps = gen.generate(n, seed, case)
    run = new_run_id()
    info = make_template(client, case, run)
    try:
        outcomes = evaluate(client, info["template"], camps, info["e0"])
        template_counts = counts(client, info["template"])
    finally:
        client.drop(info["template"])
    after = counts(client, info["base"])
    return {
        "case": case,
        "label": case_label(case),
        "n": n,
        "seed": seed,
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "definitions": DEFINITIONS,
        "campaigns_sha256": campaigns_sha256(camps),
        "e0": info["e0"],
        "campaign_day0": info["day0"],
        "scaffold": {
            "id": info["scaffold"].id,
            "keepers": info["scaffold"].keepers,
            "privileges": list(info["scaffold"].privileges),
            "history_grants": info["scaffold"].n_history_grants,
            "release_history_and_background": info["scaffold"].n_releases,
            "baseline_grant_days": list(gen.BASELINE_GRANT_DAYS),
            "release_cadence_days": gen.RELEASE_CADENCE_DAYS,
        },
        "real_graph": {
            "name": info["base"],
            "counts_before": info["real_counts_before"],
            "counts_after": after,
            "unchanged": info["real_counts_before"] == after,
            "planted_into": "copies only",
            "port": client.port,
            "baseline_check": baseline_check(
                info["base"].removeprefix("org_"), info["real_counts_before"]
            ),
        },
        "template_counts": template_counts,
        "summary": score.summarise(outcomes),
        "by_patience": by_patience(outcomes),
        "by_moves": by_moves(outcomes),
        "campaigns": [o.as_dict() for o in outcomes],
        "notes": [
            "Pressure cannot reach FIRED under the frozen detector (its keeper-activity condition "
            "is open, docs/decisions/0005); a campaign is caught through Vouch, Rush or Bypass.",
            "Rush fires only below the org's own 10th percentile of days-to-grant, so a campaign "
            "whose patience exceeds it does not fire Rush (the frozen detector as written).",
            "Detectors, conflict policy, decision policy and thresholds are unchanged: see "
            "provenance.",
        ],
        "provenance": provenance.provenance(),
        "wall_seconds": round(time.perf_counter() - start, 1),
    }


def write(doc: dict, name: str) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / name
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--case", default="tallowdate", choices=gen.CASES)
    a = ap.parse_args(argv)
    doc = run_redteam(a.case, a.n, a.seed)
    path = write(doc, f"redteam_{a.case}.json")
    s = doc["summary"]
    print(f"wrote {path}")
    print(
        f"N={s['n']} caught={s['caught']} missed={s['missed']} "
        f"detection_rate={s['detection_rate']} median_lead_days={s['median_lead_time_days']}"
    )
    print(f"real graph unchanged: {doc['real_graph']['unchanged']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
