"""Remembered normal: procedural-memory metrics as of time T (docs/HEARTHGUARD.md §7.1, §9).

Each function takes (client, org, T) and reads only events with at <= T, through the as-of
helper and the read-only guard, with an explicit timeout. T and `at` are Unix epoch seconds.

Stored as (:Normal {metric, scope, window, computed_at, value})-[:OF]->(:Org). `computed_at`
holds the as-of time T, not the wall clock, so recomputing the same T updates one node.
A metric the data cannot support is reported as NOT COMPUTED with a reason and is not stored.
"""

import time
from dataclasses import asdict, dataclass, field
from typing import Any

from core.graph.as_of import as_of_fragment, run_as_of
from core.graph.client import FalkorClient

DAY_S = 86_400
QUERY_TIMEOUT_MS = 10_000

CADENCE_WINDOW_DAYS = 730
KEEPER_WINDOW_DAYS = 90
CHANNEL_WINDOW_DAYS = 730

COMPUTED = "COMPUTED"
NOT_COMPUTED = "NOT COMPUTED"


@dataclass
class MetricResult:
    metric: str  # spec §6.1 metric name
    scope: str  # action kind the metric is about
    window: str  # e.g. '730d'
    T: int
    status: str
    value: Any = None
    unit: str | None = None
    n: int | None = None  # sample size behind the value
    reason: str | None = None
    query: str | None = None
    params: dict = field(default_factory=dict)
    query_ms: float | None = None  # wall clock around the call
    server_ms: float | None = None  # FalkorDB's own execution time

    def as_dict(self) -> dict:
        return asdict(self)


def graph_for(org: str) -> str:
    return f"org_{org}"


def _run(client: FalkorClient, org: str, cypher: str, params: dict):
    start = time.perf_counter()
    result = run_as_of(client, graph_for(org), cypher, params, timeout_ms=QUERY_TIMEOUT_MS)
    return result, (time.perf_counter() - start) * 1000


def commit_cadence_days(client: FalkorClient, org: str, T: int) -> MetricResult:
    """Median gap, in days, between consecutive commits in the trailing 730 days up to T."""
    cypher = (
        "MATCH (c:Action {kind: 'commit'}) "
        f"WHERE {as_of_fragment('c')} AND c.at > $T - $window "
        "WITH c.at AS at ORDER BY at "
        "WITH collect(at) AS ts "
        "WITH [i IN range(1, size(ts) - 1) | ts[i] - ts[i - 1]] AS gaps "
        "UNWIND gaps AS g "
        "RETURN percentileCont(g, 0.5) AS median_gap_s, count(g) AS n LIMIT 1"
    )
    params = {"T": T, "window": CADENCE_WINDOW_DAYS * DAY_S}
    res = MetricResult(
        metric="cadence_days",
        scope="commit",
        window=f"{CADENCE_WINDOW_DAYS}d",
        T=T,
        status=NOT_COMPUTED,
        unit="days",
        query=cypher,
        params=params,
    )
    r, res.query_ms = _run(client, org, cypher, params)
    res.server_ms = r.run_time_ms
    median_s, n = r.result_set[0]
    res.n = n
    if not n:
        res.reason = "fewer than 2 commits in the window, so there is no gap to take a median of"
        return res
    res.status = COMPUTED
    res.value = median_s / DAY_S
    return res


def active_keepers_as_of_T(client: FalkorClient, org: str, T: int) -> MetricResult:
    """Distinct actors with a commit in the trailing 90 days up to T."""
    cypher = (
        "MATCH (a:Actor)-[d:DID]->(c:Action {kind: 'commit'}) "
        f"WHERE {as_of_fragment('d')} AND d.at > $T - $window "
        "RETURN count(DISTINCT a) AS n LIMIT 1"
    )
    params = {"T": T, "window": KEEPER_WINDOW_DAYS * DAY_S}
    res = MetricResult(
        metric="active_keepers",
        scope="commit",
        window=f"{KEEPER_WINDOW_DAYS}d",
        T=T,
        status=NOT_COMPUTED,
        unit="actors",
        query=cypher,
        params=params,
    )
    r, res.query_ms = _run(client, org, cypher, params)
    res.server_ms = r.run_time_ms
    res.n = res.value = r.result_set[0][0]
    res.status = COMPUTED
    return res


def release_channel_as_of_T(client: FalkorClient, org: str, T: int) -> MetricResult:
    """Most common Path.channel among releases in the trailing 730 days up to T."""
    cypher = (
        "MATCH (r:Action {kind: 'release'})-[:VIA]->(p:Path) "
        f"WHERE {as_of_fragment('r')} AND r.at > $T - $window "
        "RETURN p.channel AS channel, count(r) AS n ORDER BY n DESC, channel LIMIT 10"
    )
    params = {"T": T, "window": CHANNEL_WINDOW_DAYS * DAY_S}
    res = MetricResult(
        metric="usual_path",
        scope="release",
        window=f"{CHANNEL_WINDOW_DAYS}d",
        T=T,
        status=NOT_COMPUTED,
        unit="channel",
        query=cypher,
        params=params,
    )
    r, res.query_ms = _run(client, org, cypher, params)
    res.server_ms = r.run_time_ms
    if not r.result_set:
        res.reason = "no releases in the window"
        return res
    res.status = COMPUTED
    res.value = r.result_set[0][0]
    res.n = sum(row[1] for row in r.result_set)
    return res


def not_computed(metric: str, scope: str, window: str, T: int, reason: str) -> MetricResult:
    """A metric the data cannot support. No query is run and nothing is stored."""
    return MetricResult(
        metric=metric, scope=scope, window=window, T=T, status=NOT_COMPUTED, reason=reason
    )


def keeper_activity_median_90d(T: int) -> MetricResult:
    return not_computed(
        "keeper_activity_median_90d",
        "commit",
        "90d",
        T,
        "depends on the open Pressure keeper-activity condition (spec §7.6, FREEZE draft); "
        "not computed until that freeze item is decided",
    )


def grant_days(T: int) -> MetricResult:
    return not_computed(
        "grant_days",
        "privilege",
        "all",
        T,
        "git records no grants, so no grant event is evidenced yet "
        "(eval/results/xz_grants_unknown.json)",
    )


def trusted_actor_set(T: int) -> MetricResult:
    return not_computed(
        "trusted_actor_set",
        "privilege",
        "all",
        T,
        "defined from grants, and git records no grants (eval/results/xz_grants_unknown.json)",
    )


def store(client: FalkorClient, org: str, res: MetricResult) -> None:
    """Write a computed metric as a Normal node. Idempotent per (metric, scope, window, T)."""
    if res.status != COMPUTED:
        return
    client.query(
        graph_for(org),
        """MERGE (o:Org {id: $org})
           MERGE (n:Normal {metric: $metric, scope: $scope, window: $window, computed_at: $T})
             SET n.value = $value
           MERGE (n)-[:OF]->(o)""",
        {
            "org": org,
            "metric": res.metric,
            "scope": res.scope,
            "window": res.window,
            "T": res.T,
            "value": res.value,
        },
        timeout_ms=QUERY_TIMEOUT_MS,
    )
