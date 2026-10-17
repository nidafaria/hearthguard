"""Lone keeper (docs/HEARTHGUARD.md §7.1): a risk-multiplier flag, never a move that fires alone.

The flag is set when guardians == 1 OR active_keepers == 1, as of T. No LLM.

  - guardians come from core/takeover/guardians.py. That rule is PROPOSED (decision 0001), so a
    Lone keeper result is provisional.
  - active_keepers comes from core/normal/metrics.py, which counts commit AUTHORS in the trailing
    90 days. That definition is an OPEN decision (0001), not settled.
  - If guardians is NOT COMPUTED and no approval/review graph exists for fallback,
    Lone keeper is NOT_COMPUTED.
  - §7.1 fallback: betweenness >= 0.5 on the approval/review graph, if maxFlow fails.
"""

import time

from redis.exceptions import ResponseError

from core.detectors.common import NOT_COMPUTED, DetectorResult
from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient
from core.graph.ro_guard import ro_query
from core.normal import metrics
from core.takeover import guardians as gmod
from core.takeover import scratch as sc

FLAG_SET = "FLAG_SET"
FLAG_NOT_SET = "FLAG_NOT_SET"

REVIEW_APPROVAL_QUERY = (
    "MATCH (r:Actor)-[e:REVIEWED|APPROVED]->(x:Actor) "
    "WHERE (e.at IS NULL OR e.at <= $T) "
    "RETURN DISTINCT r.hid AS src, x.hid AS dst "
    "ORDER BY src, dst LIMIT 1000"
)
ACTION_APPROVAL_QUERY = (
    "MATCH (r:Actor)-[e:APPROVED]->(a:Action)<-[:DID]-(x:Actor) "
    "WHERE (e.at IS NULL OR e.at <= $T) AND (a.at IS NULL OR a.at <= $T) "
    "RETURN DISTINCT r.hid AS src, x.hid AS dst "
    "ORDER BY src, dst LIMIT 1000"
)


def betweenness_fallback(
    client: FalkorClient,
    org: str,
    T: int,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    run: str | None = None,
) -> tuple[float | None, str | None, list[dict]]:
    """§7.1 fallback: betweenness >= 0.5 on the approval/review graph when maxFlow fails.

    Reads REVIEWED and APPROVED relationships visible at <= T. If no such relationships exist,
    returns (None, None, queries). Otherwise, builds an isolated scratch graph, executes
    algo.betweenness, and returns (top_normalized_betweenness, top_actor_hid, queries).
    """
    queries: list[dict] = []
    g_org = sc.graph_for(org)

    try:
        start = time.perf_counter()
        r1 = ro_query(client, g_org, REVIEW_APPROVAL_QUERY, {"T": T}, timeout_ms=timeout_ms)
        ms1 = (time.perf_counter() - start) * 1000
        queries.append(
            sc.QueryRecord(
                "read_reviews", REVIEW_APPROVAL_QUERY, {"T": T}, ms1, len(r1.result_set)
            ).as_dict()
        )

        start = time.perf_counter()
        r2 = ro_query(client, g_org, ACTION_APPROVAL_QUERY, {"T": T}, timeout_ms=timeout_ms)
        ms2 = (time.perf_counter() - start) * 1000
        queries.append(
            sc.QueryRecord(
                "read_action_approvals", ACTION_APPROVAL_QUERY, {"T": T}, ms2, len(r2.result_set)
            ).as_dict()
        )
    except ResponseError:
        return None, None, queries

    pairs = {(r[0], r[1]) for r in r1.result_set} | {(r[0], r[1]) for r in r2.result_set}
    # Filter out self-loops (an author cannot review their own change for betweenness)
    pairs = {(src, dst) for src, dst in pairs if src != dst}
    if not pairs:
        return None, None, queries

    nodes = {s for s, _ in pairs} | {d for _, d in pairs}
    n = len(nodes)
    if n == 1:
        top_actor = next(iter(nodes))
        return 1.0, top_actor, queries

    with sc.scratch_graph(client, run) as scratch:
        batch = [{"src": s, "dst": d} for s, d in sorted(pairs)]
        client.query(
            scratch,
            "UNWIND $rows AS r "
            "MERGE (s:Actor {hid: r.src}) "
            "MERGE (d:Actor {hid: r.dst}) "
            "MERGE (s)-[:REVIEWED]->(d)",
            {"rows": batch},
            timeout_ms=timeout_ms,
        )
        bw_query = (
            "CALL algo.betweenness({nodeLabels: ['Actor'], relationshipTypes: ['REVIEWED']}) "
            "YIELD node, score RETURN node.hid AS hid, score ORDER BY score DESC LIMIT 1000"
        )
        start = time.perf_counter()
        r_bw = client.query(scratch, bw_query, timeout_ms=timeout_ms)
        ms_bw = (time.perf_counter() - start) * 1000
        queries.append(
            sc.QueryRecord("betweenness", bw_query, {}, ms_bw, len(r_bw.result_set)).as_dict()
        )

    if not r_bw.result_set:
        return None, None, queries

    top_actor, raw_score = r_bw.result_set[0]
    if n >= 3:
        # Normalized directed betweenness: score / ((n - 1) * (n - 2))
        norm_score = float(raw_score) / ((n - 1) * (n - 2))
    elif n == 2:
        norm_score = 0.0
    else:
        norm_score = 1.0

    return norm_score, top_actor, queries


def lone_keeper(
    client: FalkorClient,
    org: str,
    privilege_kind: str,
    T: int,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    run: str | None = None,
    force_fallback: bool = False,
) -> DetectorResult:
    T = sc.checked_time(T)
    res = DetectorResult(
        "lone_keeper", org, T, NOT_COMPUTED, provisional=True, flag=None, multiplier_only=True
    )

    used_fallback = False
    by_guardians = False
    bw_score = None
    bw_top = None

    if not force_fallback:
        try:
            g = gmod.guardians(client, org, privilege_kind, T, timeout_ms, run=run)
            res.queries = list(g.queries)
        except Exception:
            g = None
    else:
        g = None

    if force_fallback or (g is not None and g.status != gmod.COMPUTED):
        # Fallback if maxFlow fails (§7.1): betweenness >= 0.5 on the approval/review graph
        bw_score, bw_top, bw_queries = betweenness_fallback(client, org, T, timeout_ms, run=run)
        res.queries.extend(bw_queries)
        if bw_score is not None:
            used_fallback = True
            by_guardians = bw_score >= 0.5
        else:
            reason = g.reason if g is not None else "forced fallback: no approval/review graph"
            res.reason = f"guardians not computed: {reason}"
            res.query_ms = sum(q["ms"] for q in res.queries)
            return res
    else:
        by_guardians = g.guardians == 1

    keepers = metrics.active_keepers_as_of_T(client, org, T)
    res.queries.append(
        sc.QueryRecord("active_keepers", keepers.query, keepers.params, keepers.query_ms).as_dict()
    )
    res.query_ms = sum(q["ms"] for q in res.queries)

    by_keepers = keepers.value == 1
    res.flag = by_guardians or by_keepers
    res.status = FLAG_SET if res.flag else FLAG_NOT_SET

    guardians_label = "betweenness >= 0.5 (fallback)" if used_fallback else "guardians == 1"
    not_guardians_label = "betweenness < 0.5 (fallback)" if used_fallback else "guardians != 1"

    if res.flag:
        parts = []
        if by_guardians:
            parts.append(guardians_label)
        if by_keepers:
            parts.append("active_keepers == 1")
        res.reason = "multiplier flag set: " + " and ".join(parts)
    else:
        res.reason = f"multiplier flag not set: {not_guardians_label} and active_keepers != 1"

    res.evidence = {
        "guardians": g.guardians if g is not None else None,
        "active_keepers": keepers.value,
        "guardians_is_1": by_guardians if not used_fallback else None,
        "active_keepers_is_1": by_keepers,
        "rule": sc.RULE,
        "active_keepers_definition": "distinct commit authors in the trailing 90 days (OPEN, 0001)",
    }
    if used_fallback:
        res.evidence.update(
            {
                "guardians_fallback": "betweenness",
                "betweenness_score": bw_score,
                "betweenness_top_actor": bw_top,
                "betweenness_ge_half": by_guardians,
            }
        )
    return res
