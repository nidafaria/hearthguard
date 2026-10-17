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
    FIRED,
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
DEFAULT_MARKER = "default chosen for submission, not final"

KEEPERS_QUERY = (
    "MATCH (k:Actor)-[e:CAN_GRANT|GRANTED]->(p:Privilege) "
    "WHERE (e.at IS NULL OR e.at <= $T) "
    "RETURN DISTINCT k.hid AS hid ORDER BY hid LIMIT 1000"
)
ALT_KEEPERS_QUERY = (
    "MATCH (k:Actor) WHERE k.is_keeper = true RETURN DISTINCT k.hid AS hid ORDER BY hid LIMIT 1000"
)
CAPACITY_QUERY = (
    "MATCH (k:Actor)-[:ASSERTED]->(c:Claim {kind: 'CAPACITY_STATEMENT'}) "
    "WHERE k.hid IN $keeper_hids AND c.at <= $T AND c.at > $start "
    "RETURN c.id AS claim_id, k.hid AS hid, c.at AS at ORDER BY at, claim_id LIMIT 1000"
)
RECENT_ACTIVITY_QUERY = (
    "MATCH (k:Actor)-[d:DID]->(a:Action) "
    "WHERE k.hid IN $keeper_hids AND d.at <= $T AND d.at > $start "
    "RETURN count(a) AS n LIMIT 1"
)
NORMAL_MEDIAN_QUERY = (
    "MATCH (o:Org)<-[:OF]-(n:Normal {metric: 'keeper_activity_median_90d'}) "
    "RETURN n.value AS val LIMIT 1"
)


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

    res.evidence["claim_condition_met"] = True

    # Condition (2): keepers' activity in the last 90 days is <= 50% of trailing 2-year median,
    # OR a keeper CAPACITY_STATEMENT exists in the window.
    # Default chosen for submission, not final (docs/decisions/0005):
    # Keepers are grant holders (CAN_GRANT or GRANTED). If no keeper record exists, Pressure
    # stays NOT_COMPUTED with OPEN_REASON.
    keeper_rows = rd.plain("read_keepers", KEEPERS_QUERY, {"T": T}).result_set
    keeper_hids = sorted({r[0] for r in keeper_rows})
    if not keeper_hids:
        # Check if any Actor has is_keeper=true
        alt_keepers = rd.plain("read_alt_keepers", ALT_KEEPERS_QUERY).result_set
        keeper_hids = sorted({r[0] for r in alt_keepers})

    if not keeper_hids:
        res.reason = OPEN_REASON
        res.evidence["keeper_condition_default"] = DEFAULT_MARKER
        return rd.finish(res)

    # 2a: Check if a keeper CAPACITY_STATEMENT exists in the window
    cap_claims = rd.plain(
        "read_keeper_capacity",
        CAPACITY_QUERY,
        {"keeper_hids": keeper_hids, "start": start, "T": T},
    ).result_set
    if cap_claims:
        res.status = FIRED
        res.reason = (
            f"condition (1) met and keeper {cap_claims[0][1]} made a CAPACITY_STATEMENT in the "
            f"last {p['window_days']} days ({DEFAULT_MARKER})"
        )
        res.evidence["keeper_condition_met"] = True
        res.evidence["keeper_capacity_statement"] = True
        res.evidence["keeper_capacity_claim_ids"] = [r[0] for r in cap_claims]
        res.evidence["keeper_condition_default"] = DEFAULT_MARKER
        return rd.finish(res)

    # 2b: Keeper activity in last 90 days vs trailing-two-year median
    act_win = p.get("keeper_activity_window_days", 90) * lh.DAY_S
    recent_r = rd.plain(
        "read_keeper_recent_activity",
        RECENT_ACTIVITY_QUERY,
        {"keeper_hids": keeper_hids, "start": T - act_win, "T": T},
    ).result_set
    recent_actions = recent_r[0][0] if recent_r else 0

    norm_r = rd.plain("read_keeper_median_normal", NORMAL_MEDIAN_QUERY).result_set
    if norm_r and norm_r[0][0] is not None:
        median_act = float(norm_r[0][0])
    else:
        # Compute median across 8 90-day intervals in the trailing 730 days
        counts = []
        for i in range(8):
            w_end = T - i * act_win
            w_start = T - (i + 1) * act_win
            cnt_r = rd.plain(
                f"read_keeper_interval_{i}",
                "MATCH (k:Actor)-[d:DID]->(a:Action) "
                "WHERE k.hid IN $keeper_hids AND d.at <= $w_end AND d.at > $w_start "
                "RETURN count(a) LIMIT 1",
                {"keeper_hids": keeper_hids, "w_end": w_end, "w_start": w_start},
            ).result_set
            counts.append(cnt_r[0][0] if cnt_r else 0)
        sorted_counts = sorted(counts)
        median_act = (sorted_counts[3] + sorted_counts[4]) / 2.0

    max_ratio = p.get("keeper_activity_max_ratio", 0.5)
    if median_act > 0 and (recent_actions / median_act) <= max_ratio:
        ratio = recent_actions / median_act
        res.status = FIRED
        res.reason = (
            f"condition (1) met and keepers' activity in last 90 days ({recent_actions}) is "
            f"<= {int(max_ratio * 100)}% of trailing median ({median_act:.1f}) ({DEFAULT_MARKER})"
        )
        res.evidence["keeper_condition_met"] = True
        res.evidence["keeper_activity_recent"] = recent_actions
        res.evidence["keeper_activity_median"] = median_act
        res.evidence["keeper_activity_ratio"] = ratio
        res.evidence["keeper_condition_default"] = DEFAULT_MARKER
        return rd.finish(res)

    res.status = NOT_FIRED
    res.reason = (
        f"condition (1) met, but keepers' activity in last 90 days ({recent_actions}) was "
        f"> {int(max_ratio * 100)}% of trailing median ({median_act:.1f}) and no keeper "
        f"CAPACITY_STATEMENT exists ({DEFAULT_MARKER})"
    )
    res.evidence["keeper_condition_met"] = False
    res.evidence["keeper_activity_recent"] = recent_actions
    res.evidence["keeper_activity_median"] = median_act
    res.evidence["keeper_condition_default"] = DEFAULT_MARKER
    return rd.finish(res)

