"""Pressure detector (docs/HEARTHGUARD.md §7.1).

Fires when, in the last 120 days up to T:
  (1) there are >= 3 PRESSURE or URGENCY claims from >= 2 distinct actors who are low-history
      (history < 90 days or < 5 actions; core/detectors/low_history.py), AND
  (2) the keepers' activity in the last 90 days is <= 50% of this org's own trailing-two-year
      median, OR a keeper CAPACITY_STATEMENT exists in the window.
All thresholds are in config/frozen.yaml. The claims come from the Reader (an LLM); the
detector itself is plain code. If the Reader is unavailable the caller records HOLD.

Condition (2) is OPEN in the freeze: who counts as a keeper is not decided (docs/decisions/
0001, "Active keepers"), and no grant record exists for xz. So this detector never returns FIRED
from real data. It still computes condition (1):
  - if (1) fails, (1) AND (2) is false whatever (2) is -> NOT_FIRED, with the counts;
  - if (1) holds -> NOT_COMPUTED, reason "keeper activity condition open in freeze".
Example (hand check): claims by low-history A, B, B -> 3 claims, 2 actors -> (1) holds;
claims by A, A, A -> 3 claims, 1 actor -> (1) fails.
"""

from core.detectors import low_history as lh
from core.detectors.common import (
    NOT_COMPUTED,
    NOT_FIRED,
    DetectorResult,
    Reader,
)
from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient
from core.takeover import scratch as sc

KINDS = ["PRESSURE", "URGENCY"]
CLAIMS_QUERY = (
    "MATCH (a:Actor)-[:ASSERTED]->(c:Claim) "
    "WHERE c.kind IN $kinds AND c.at <= $T AND c.at > $start "
    "RETURN a.hid AS hid, c.id AS claim_id, c.kind AS kind, c.at AS at ORDER BY at, claim_id"
)
OPEN_REASON = "keeper activity condition open in freeze"


def pressure(
    client: FalkorClient, org: str, T: int, timeout_ms: int = DEFAULT_TIMEOUT_MS
) -> DetectorResult:
    T = sc.checked_time(T)
    p = lh.thresholds()["pressure"]
    res = DetectorResult("pressure", org, T, NOT_COMPUTED)
    rd = Reader(client, org, T, timeout_ms)

    start = T - p["window_days"] * lh.DAY_S
    claims = rd.paged("read_claims", CLAIMS_QUERY, {"kinds": KINDS, "start": start})
    hids = sorted({r[0] for r in claims})
    hist = lh.history(rd, hids) if hids else {}
    if isinstance(hist, str):
        res.reason = hist
        return rd.finish(res)

    low = {
        h for h, v in hist.items() if lh.is_low(v, p["low_history_days"], p["low_history_actions"])
    }
    low_claims = [r for r in claims if r[0] in low]
    n_actors = len({r[0] for r in low_claims})
    res.evidence = {
        "window_days": p["window_days"],
        "claims_in_window": len(claims),
        "claims_by_low_history_actors": len(low_claims),
        "low_history_actors": n_actors,
        "claim_ids": [r[1] for r in low_claims][:50],
        "min_claims": p["min_claims"],
        "min_distinct_actors": p["min_distinct_actors"],
    }
    if len(low_claims) < p["min_claims"] or n_actors < p["min_distinct_actors"]:
        res.status = NOT_FIRED
        res.reason = (
            f"{len(low_claims)} PRESSURE/URGENCY claims from {n_actors} low-history actors in the "
            f"last {p['window_days']} days; need {p['min_claims']} claims from "
            f"{p['min_distinct_actors']} actors"
        )
        return rd.finish(res)

    res.reason = OPEN_REASON
    res.evidence["claim_condition_met"] = True
    return rd.finish(res)
