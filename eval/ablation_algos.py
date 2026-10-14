"""Algorithm ablation (spec §10.2): turn the graph algorithms off one at a time.

  uv run python -m eval.ablation_algos --n 100 --seed 7 --case tallowdate

Arms, on the SAME attack and clean campaigns, scored by the frozen detectors and
decide_with_unknowns():
  baseline          everything on
  vouch_graph_off   Vouch without SHARES edges and components: it fires on two low-history vouchers
                    for one candidate, nothing more. (The spec names WCC / labelPropagation; the
                    frozen detector computes its components in plain code, core/detectors/vouch.py
                    `components`, so this arm removes that component step, whatever runs it.)
  sppaths_off       takeover cost and trust path (algo.SPpaths) replaced by a stub that counts its
                    calls and returns NOT COMPUTED. If the decision never calls them, nothing
                    changes, and the file says so with the call count.
  maxflow_off       guardians (algo.maxFlow minimum vertex cut) replaced by the number of distinct
                    keepers who can grant the privilege, with no cut. It feeds Lone keeper.

Detectors, policies and thresholds are not edited. The ablated function is swapped in for the run
only (unittest.mock.patch.object) and the arm's own code lives in this file. Writes
eval/results/ablation_algos.json with detection rate and false-alarm rate per arm and their change
from baseline. Published as measured: an arm that ties the baseline is reported as tied.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

from core.detectors import low_history as lh
from core.detectors import vouch as vouch_mod
from core.detectors.common import FIRED, NOT_COMPUTED, NOT_FIRED, DetectorResult, Reader
from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient
from core.hardening.simulate import counts
from core.takeover import cost as cost_mod
from core.takeover import guardians as gmod
from core.takeover import scratch as sc
from core.takeover import trust_path as tp_mod
from redteam import generate as gen
from redteam import provenance, run, score

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "eval" / "results" / "ablation_algos.json"

ARMS = ("baseline", "vouch_graph_off", "sppaths_off", "maxflow_off")
ARM_TEXT = {
    "baseline": "every algorithm on",
    "vouch_graph_off": "Vouch fires on >= 2 low-history vouchers for one candidate; no SHARES "
    "edges, no components, no signal-type count",
    "sppaths_off": "takeover cost and trust path (algo.SPpaths) stubbed out; calls counted",
    "maxflow_off": "guardians = distinct keepers who can grant the privilege (no maxFlow cut)",
}

DEFINITIONS = {
    "detection_rate": "caught / n on attack campaigns (NOTE or WATCH at any move point)",
    "false_alarm_rate": "flagged / n on clean campaigns (the same test on benign campaigns)",
    "delta": "arm minus baseline, on the same campaigns",
    "verdict": "worse / tied / better from the two deltas, no rounding",
}


def vouch_without_graph(
    client: FalkorClient, org: str, T: int, timeout_ms: int = DEFAULT_TIMEOUT_MS
) -> DetectorResult:
    """Vouch with the SHARES / component step removed. Everything before it is the frozen code."""
    T = sc.checked_time(T)
    v = lh.thresholds()["vouch"]
    res = DetectorResult("vouch", org, T, NOT_COMPUTED)
    rd = Reader(client, org, T, timeout_ms)
    claims = rd.paged("read_vouch_claims", vouch_mod.CLAIMS_QUERY)
    hids = sorted({r[0] for r in claims})
    hist = lh.history(rd, hids) if hids else {}
    if isinstance(hist, str):
        res.reason = hist
        return rd.finish(res)
    low = {
        h for h, x in hist.items() if lh.is_low(x, v["low_history_days"], v["low_history_actions"])
    }
    by_target: dict[str, set[str]] = {}
    for hid, _cid, target, _at in (r for r in claims if r[0] in low):
        if target:
            by_target.setdefault(target, set()).add(hid)
    if not by_target:
        res.status = NOT_FIRED if len(low) < v["min_vouchers"] else NOT_COMPUTED
        res.reason = "no candidate with low-history vouchers"
        return rd.finish(res)
    if any(len(s) >= v["min_vouchers"] for s in by_target.values()):
        res.status = FIRED
        res.reason = "ablation: >= min_vouchers low-history vouchers for one candidate"
    else:
        res.status = NOT_FIRED
        res.reason = "ablation: no candidate has enough low-history vouchers"
    return rd.finish(res)


def keeper_count_guardians(
    client: FalkorClient,
    org: str,
    privilege_kind: str,
    T: int,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    run: str | None = None,
) -> gmod.GuardiansResult:
    """Guardians with no maxFlow: how many distinct keepers hold CAN_GRANT on the privilege at T."""
    T = sc.checked_time(T)
    res = gmod.GuardiansResult(org=org, privilege=privilege_kind, T=T, status=gmod.NOT_COMPUTED)
    exists, rec = sc.privilege_exists(client, org, privilege_kind, timeout_ms)
    res.queries.append(rec.as_dict())
    if not exists:
        res.reason = sc.no_data_reason(org, rec)
        return res
    grants = sc.read_grants(client, org, privilege_kind, T, ("CAN_GRANT",), timeout_ms)
    res.queries += [q.as_dict() for q in grants.queries]
    res.status = gmod.COMPUTED
    res.guardians = len({r["hid"] for r in grants.rows})
    return res


class CallCounter:
    """A stand-in for takeover cost / trust path; records calls from the decision path."""

    def __init__(self, name: str):
        self.name, self.calls = name, 0

    def __call__(self, *a, **k):
        self.calls += 1
        raise RuntimeError(f"{self.name} was called from the decision path")


def arm_patches(arm: str, stack: ExitStack) -> dict[str, CallCounter]:
    counters: dict[str, CallCounter] = {}
    if arm == "vouch_graph_off":
        stack.enter_context(mock.patch.object(vouch_mod, "vouch", vouch_without_graph))
    elif arm == "sppaths_off":
        for mod, attr in ((cost_mod, "takeover_cost"), (tp_mod, "trust_path")):
            counters[attr] = CallCounter(attr)
            stack.enter_context(mock.patch.object(mod, attr, counters[attr]))
    elif arm == "maxflow_off":
        stack.enter_context(mock.patch.object(gmod, "guardians", keeper_count_guardians))
    return counters


def rates(attack: list[score.Outcome], clean: list[score.Outcome]) -> dict:
    s = score.summarise(attack)
    flagged = sum(1 for o in clean if o.caught)
    return {
        "attack": s,
        "clean": {
            "n": len(clean),
            "flagged": flagged,
            "false_alarm_rate": (flagged / len(clean)) if clean else None,
        },
    }


def _sub(a, b):
    return None if a is None or b is None else round(a - b, 6)


def compare(base: dict, arm: dict) -> dict:
    d = {
        "detection_rate": _sub(arm["attack"]["detection_rate"], base["attack"]["detection_rate"]),
        "false_alarm_rate": _sub(
            arm["clean"]["false_alarm_rate"], base["clean"]["false_alarm_rate"]
        ),
        "median_lead_time_days": _sub(
            arm["attack"]["median_lead_time_days"], base["attack"]["median_lead_time_days"]
        ),
    }
    dr, fa = d["detection_rate"], d["false_alarm_rate"]
    if dr is None:
        v = "not computed"
    elif dr == 0 and not fa:
        v = "tied with baseline"
    else:
        parts = []
        if dr:
            parts.append("lower detection" if dr < 0 else "higher detection")
        if fa:
            parts.append("more false alarms" if fa > 0 else "fewer false alarms")
        v = ", ".join(parts) + " than baseline"
    return {"delta": d, "verdict": v}


def run_ablation(
    case: str, n: int, seed: int, n_clean: int, client: FalkorClient | None = None
) -> dict:
    client = client or FalkorClient()
    start = time.perf_counter()
    real = f"org_{case}"
    before = counts(client, real)
    camps = gen.generate(n, seed, case)
    clean = gen.clean_campaigns(n_clean, seed, case)
    info = run.make_template(client, case, run.new_run_id())
    arms: dict[str, dict] = {}
    try:
        for arm in ARMS:
            with ExitStack() as stack:
                counters = arm_patches(arm, stack)
                attack = run.evaluate(client, info["template"], camps, info["e0"])
                benign = run.evaluate(client, info["template"], clean, info["e0"])
            arms[arm] = {
                "what": ARM_TEXT[arm],
                **rates(attack, benign),
                "stub_calls": {k: c.calls for k, c in counters.items()},
                "decisions_equal_baseline": None,
                "_attack": attack,
                "_clean": benign,
            }
    finally:
        client.drop(info["template"])
    base = arms["baseline"]
    for arm, data in arms.items():
        same = [
            [(p["moves"], p["decision"]) for p in a.points]
            == [(p["moves"], p["decision"]) for p in b.points]
            for a, b in zip(
                data["_attack"] + data["_clean"], base["_attack"] + base["_clean"], strict=True
            )
        ]
        data["decisions_equal_baseline"] = {"campaigns_identical": sum(same), "of": len(same)}
        if arm != "baseline":
            data["versus_baseline"] = compare(base, data)
    for data in arms.values():
        data.pop("_attack"), data.pop("_clean")
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
        "arms": arms,
        "real_graph": {
            "name": real,
            "counts_before": before,
            "counts_after": after,
            "unchanged": before == after,
            "port": client.port,
        },
        "notes": [
            "Published as measured. A tie is reported as a tie.",
            "Takeover cost and trust path are not inputs to decide_with_unknowns(); the "
            "sppaths_off arm records how many times they were called (stub_calls). Their value "
            "shows in the measured structure (eval/results/hardening_redteam_*.json), not here.",
            "The clean set has no VOUCH or PRESSURE claims, so it cannot show a Vouch false alarm; "
            "the false-alarm study (`make false-positives`) is the measurement for that.",
            "Campaigns and scaffold are synthetic; three real attacks are too few to claim "
            "precision (spec §10.2).",
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
        print(
            f"{name:<16} detection={arm['attack']['detection_rate']} "
            f"false_alarm={arm['clean']['false_alarm_rate']} "
            f"{arm.get('versus_baseline', {}).get('verdict', '')}"
        )
    print(f"real graph unchanged: {doc['real_graph']['unchanged']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
