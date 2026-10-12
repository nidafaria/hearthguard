"""Vouch detector (docs/HEARTHGUARD.md §7.1).

Fires when >= 2 low-history actors VOUCH for the same candidate AND those actors fall in the
same component over SHARES edges that together carry >= 2 distinct signal types.
All thresholds are in config/frozen.yaml. The claims come from the Reader; the rest is plain code.

What can be established from the data, in order (each step can end the run):
  1. Count low-history actors with a VOUCH claim at <= T. If fewer than 2 -> NOT_FIRED.
  2. The candidate: a VOUCH claim names its candidate in Claim.target_hid. The Reader does not
     extract a target, so on real data it is empty. If >= 2 low-history vouchers exist but their
     claims carry no target -> NOT_COMPUTED (the same candidate cannot be established).
  3. For each candidate with >= 2 low-history vouchers: read the SHARES edges between them.
     If there are none -> NOT_COMPUTED (no SHARES edges built).
  4. Components over those SHARES edges. Fires if a component holds >= 2 of the vouchers and the
     SHARES edges inside it carry >= 2 distinct signal types.
SHARES carries no time, so it must only ever be built from facts public at T.
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

CLAIMS_QUERY = (
    "MATCH (a:Actor)-[:ASSERTED]->(c:Claim {kind: 'VOUCH'}) WHERE c.at <= $T "
    "RETURN a.hid AS hid, c.id AS claim_id, c.target_hid AS target, c.at AS at "
    "ORDER BY at, claim_id"
)
SHARES_QUERY = (
    "MATCH (a:Actor)-[s:SHARES]->(b:Actor) WHERE a.hid IN $hids AND b.hid IN $hids "
    "RETURN a.hid AS a, b.hid AS b, s.signal AS signal ORDER BY a, b, signal LIMIT 1000"
)


def components(edges: list[tuple[str, str]], nodes: list[str]) -> list[set[str]]:
    """Connected components of the given SHARES edges over the given actors."""
    parent = {n: n for n in nodes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        if a in parent and b in parent:
            parent[find(a)] = find(b)
    groups: dict[str, set[str]] = {}
    for n in nodes:
        groups.setdefault(find(n), set()).add(n)
    return list(groups.values())


def vouch(
    client: FalkorClient, org: str, T: int, timeout_ms: int = DEFAULT_TIMEOUT_MS
) -> DetectorResult:
    T = sc.checked_time(T)
    v = lh.thresholds()["vouch"]
    res = DetectorResult("vouch", org, T, NOT_COMPUTED)
    rd = Reader(client, org, T, timeout_ms)

    claims = rd.paged("read_vouch_claims", CLAIMS_QUERY)
    hids = sorted({r[0] for r in claims})
    hist = lh.history(rd, hids) if hids else {}
    if isinstance(hist, str):
        res.reason = hist
        return rd.finish(res)
    low = {
        h for h, x in hist.items() if lh.is_low(x, v["low_history_days"], v["low_history_actions"])
    }
    low_claims = [r for r in claims if r[0] in low]
    n_vouchers = len({r[0] for r in low_claims})
    res.evidence = {
        "vouch_claims": len(claims),
        "low_history_vouchers": n_vouchers,
        "min_vouchers": v["min_vouchers"],
        "min_signal_types": v["min_signal_types"],
    }
    if n_vouchers < v["min_vouchers"]:
        res.status = NOT_FIRED
        res.reason = f"{n_vouchers} low-history actors vouched; need {v['min_vouchers']}"
        return rd.finish(res)

    by_target: dict[str, set[str]] = {}
    for hid, _cid, target, _at in low_claims:
        if target:
            by_target.setdefault(target, set()).add(hid)
    if not by_target:
        res.reason = "VOUCH claims carry no target: the same candidate cannot be established"
        return rd.finish(res)

    groups = {t: sorted(s) for t, s in by_target.items() if len(s) >= v["min_vouchers"]}
    if not groups:
        res.status = NOT_FIRED
        res.reason = f"no candidate has {v['min_vouchers']} low-history vouchers"
        return rd.finish(res)

    all_ids = sorted({h for g in groups.values() for h in g})
    shares = rd.plain("read_shares", SHARES_QUERY, {"hids": all_ids}).result_set
    if not shares:
        res.reason = "no SHARES edges built between the vouchers"
        res.evidence["candidates_with_enough_vouchers"] = len(groups)
        return rd.finish(res)

    for _target, members in sorted(groups.items()):
        edges = [(a, b) for a, b, _s in shares if a in members and b in members]
        for comp in components(edges, members):
            if len(comp) < v["min_vouchers"]:
                continue
            signals = {s for a, b, s in shares if a in comp and b in comp}
            if len(signals) >= v["min_signal_types"]:
                res.status = FIRED
                res.reason = (
                    f"{len(comp)} low-history vouchers for one candidate share a component "
                    f"with {len(signals)} signal types"
                )
                res.evidence.update({"component_size": len(comp), "signal_types": sorted(signals)})
                return rd.finish(res)
    res.status = NOT_FIRED
    res.reason = "no component of vouchers carries enough distinct signal types"
    return rd.finish(res)
