"""Memory ablation (spec §10.2, §13.7): the same frozen detectors, full against forgetful memory.

  uv run python -m eval.ablation_memory --n 100 --seed 7 --case tallowdate

Arms: `full` (the whole graph), `forget_90` and `forget_30` (only the last 90 or 30 days, no
remembered normal, no visibility memory; redteam/score.py forget()). The SAME campaigns are planted
for every arm, one copy per campaign, and the frozen detectors and decide_with_unknowns() judge each
one at its own move times. Nothing about a detector, the conflict policy or the decision policy
changes between arms; only what the graph remembers does.

Writes eval/results/ablation_memory.json: per arm and per attacker patience, detection rate and
median lead time, and the same on a set of clean campaigns (flag rate). The Patience screen
(ui/src/Patience.tsx) reads this file. Whatever it shows is published as measured, including a tie
or a result that is unflattering to the memory claim (spec §10.2, the Lethe rule).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from core.graph.client import FalkorClient
from core.hardening.simulate import counts
from redteam import generate as gen
from redteam import provenance, run, score

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "eval" / "results"
OUT = RESULTS / "ablation_memory.json"

# arm name -> memory window in days (None is full memory)
ARMS: dict[str, int | None] = {"full": None, "forget_90": 90, "forget_30": 30}
TIE_TOLERANCE = 0.0  # a difference of zero is a tie; nothing is rounded into one

DEFINITIONS = {
    **{k: run.DEFINITIONS[k] for k in ("caught", "lead_time_days", "detection_rate")},
    "forget_W": "a copy of the template with every event older than T - W days removed, no Normal "
    "node, no visibility edge or Place, no remembered first-seen time (redteam/score.py forget); "
    "the detectors then run unchanged as of T",
    "patience_days": "days from the attacker's first action to the privilege grant",
    "false_flag_rate": "flagged / n on clean campaigns: NOTE or WATCH at any point of a benign "
    "campaign (a new contributor granted at a normal pace, then a release on the normal path)",
    "delta": "arm minus full, on the same campaigns",
    "verdict": "better / tied / worse is stated per patience level from the paired counts, with "
    "no rounding and no significance claim; n per level is small",
}


def patience_rows(outcomes: list[score.Outcome]) -> list[dict]:
    groups: dict[int, list[score.Outcome]] = defaultdict(list)
    for o in outcomes:
        groups[o.patience_days].append(o)
    return [{"patience_days": p, **score.summarise(groups[p])} for p in sorted(groups)]


def delta(full: dict | None, arm: dict | None) -> dict:
    """Arm minus full for one summary row. Null where either side has no value."""

    def sub(a, b):
        return None if a is None or b is None else round(a - b, 6)

    f, a = full or {}, arm or {}
    return {
        "detection_rate": sub(a.get("detection_rate"), f.get("detection_rate")),
        "median_lead_time_days": sub(
            a.get("median_lead_time_days"), f.get("median_lead_time_days")
        ),
    }


def verdict(d: dict) -> str:
    """Words for one delta, from the numbers only. Detection rate first, lead time second."""
    rate, lead = d["detection_rate"], d["median_lead_time_days"]
    if rate is None:
        return "not computed"
    if rate < -TIE_TOLERANCE:
        return "worse than full memory (lower detection rate)"
    if rate > TIE_TOLERANCE:
        return "better than full memory (higher detection rate)"
    if lead is None or lead == 0:
        return "tied with full memory"
    return (
        "same detection rate, shorter lead time"
        if lead < 0
        else "same detection rate, longer lead time"
    )


def comparison(arms: dict[str, dict]) -> dict:
    full = arms["full"]
    out = {}
    for name, arm in arms.items():
        if name == "full":
            continue
        by_p = {r["patience_days"]: r for r in full["by_patience"]}
        rows = []
        for r in arm["by_patience"]:
            d = delta(by_p.get(r["patience_days"]), r)
            rows.append({"patience_days": r["patience_days"], "delta": d, "verdict": verdict(d)})
        total = delta(full["summary"], arm["summary"])
        out[name] = {"overall": {"delta": total, "verdict": verdict(total)}, "by_patience": rows}
    return out


def run_ablation(
    case: str, n: int, seed: int, n_clean: int, client: FalkorClient | None = None
) -> dict:
    client = client or FalkorClient()
    start = time.perf_counter()
    real = f"org_{case}"
    before = counts(client, real)
    camps = gen.generate(n, seed, case)
    clean = gen.clean_campaigns(n_clean, seed, case) if n_clean else []
    info = run.make_template(client, case, run.new_run_id())
    arms: dict[str, dict] = {}
    try:
        for name, window in ARMS.items():
            attack = run.evaluate(
                client, info["template"], camps, info["e0"], memory_window_days=window
            )
            benign = (
                run.evaluate(client, info["template"], clean, info["e0"], memory_window_days=window)
                if clean
                else []
            )
            flagged = sum(1 for o in benign if o.caught)
            arms[name] = {
                "memory_window_days": window,
                "summary": score.summarise(attack),
                "by_patience": patience_rows(attack),
                "clean": {
                    "n": len(benign),
                    "flagged": flagged,
                    "false_flag_rate": (flagged / len(benign)) if benign else None,
                },
                "campaigns": [
                    {k: v for k, v in o.as_dict().items() if k != "points"} for o in attack
                ],
            }
    finally:
        client.drop(info["template"])
    after = counts(client, real)
    return {
        "case": case,
        "label": run.case_label(case, before),
        "n": n,
        "n_clean": n_clean,
        "seed": seed,
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "definitions": DEFINITIONS,
        "campaigns_sha256": run.campaigns_sha256(camps),
        "e0": info["e0"],
        "patience_levels": sorted({c.patience_days for c in camps}),
        "arms": arms,
        "comparison": comparison(arms),
        "real_graph": {
            "name": real,
            "counts_before": before,
            "counts_after": after,
            "unchanged": before == after,
            "port": client.port,
        },
        "notes": [
            "Published as measured. A tie is reported as a tie.",
            "The campaigns and the scaffold are synthetic; this is not a finding about any "
            "project. Three real attacks are too few to claim precision (spec §10.2).",
            "Detectors, conflict policy, decision policy and thresholds are unchanged between "
            "arms: see provenance.",
        ],
        "provenance": provenance.provenance(),
        "wall_seconds": round(time.perf_counter() - start, 1),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--n-clean", type=int, default=20)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--case", default="tallowdate", choices=gen.CASES)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    doc = run_ablation(a.case, a.n, a.seed, a.n_clean)
    path = Path(a.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path}")
    for name, arm in doc["arms"].items():
        s = arm["summary"]
        print(
            f"{name:<10} detection={s['detection_rate']} lead={s['median_lead_time_days']} "
            f"clean_flagged={arm['clean']['flagged']}/{arm['clean']['n']}"
        )
    print(f"real graph unchanged: {doc['real_graph']['unchanged']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
