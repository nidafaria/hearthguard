"""Lone keeper (docs/HEARTHGUARD.md §7.1): a risk-multiplier flag, never a move that fires alone.

The flag is set when guardians == 1 OR active_keepers == 1, as of T. No LLM.

  - guardians come from core/takeover/guardians.py. That rule is PROPOSED (decision 0001), so a
    Lone keeper result is provisional.
  - active_keepers comes from core/normal/metrics.py, which counts commit AUTHORS in the trailing
    90 days. That definition is an OPEN decision (0001), not settled.
  - If guardians is NOT COMPUTED, Lone keeper is NOT_COMPUTED. There is no silent fallback.

TODO: the §7.1 fallback (betweenness >= 0.5 on the approval/review graph, if maxFlow fails) is
not built in this step.
"""

from core.detectors.common import NOT_COMPUTED, DetectorResult
from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient
from core.normal import metrics
from core.takeover import guardians as gmod
from core.takeover import scratch as sc

FLAG_SET = "FLAG_SET"
FLAG_NOT_SET = "FLAG_NOT_SET"


def lone_keeper(
    client: FalkorClient,
    org: str,
    privilege_kind: str,
    T: int,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    run: str | None = None,
) -> DetectorResult:
    T = sc.checked_time(T)
    res = DetectorResult(
        "lone_keeper", org, T, NOT_COMPUTED, provisional=True, flag=None, multiplier_only=True
    )

    g = gmod.guardians(client, org, privilege_kind, T, timeout_ms, run=run)
    res.queries = list(g.queries)
    if g.status != gmod.COMPUTED:
        res.reason = f"guardians not computed: {g.reason}"
        res.query_ms = sum(q["ms"] for q in res.queries)
        return res

    keepers = metrics.active_keepers_as_of_T(client, org, T)
    res.queries.append(
        sc.QueryRecord("active_keepers", keepers.query, keepers.params, keepers.query_ms).as_dict()
    )
    res.query_ms = sum(q["ms"] for q in res.queries)

    by_guardians = g.guardians == 1
    by_keepers = keepers.value == 1
    res.flag = by_guardians or by_keepers
    res.status = FLAG_SET if res.flag else FLAG_NOT_SET
    res.reason = (
        "multiplier flag set: "
        + " and ".join(
            name
            for name, on in (("guardians == 1", by_guardians), ("active_keepers == 1", by_keepers))
            if on
        )
        if res.flag
        else "multiplier flag not set: guardians != 1 and active_keepers != 1"
    )
    res.evidence = {
        "guardians": g.guardians,
        "active_keepers": keepers.value,
        "guardians_is_1": by_guardians,
        "active_keepers_is_1": by_keepers,
        "rule": sc.RULE,
        "active_keepers_definition": "distinct commit authors in the trailing 90 days (OPEN, 0001)",
    }
    return res
