"""Takeover cost (docs/HEARTHGUARD.md §2.2, §7.4): the fewest approvals an outsider must win.

PROPOSED rule, provisional output (docs/decisions/0001-outsider-edges.md). Computed with
algo.SPpaths and weightProp 'approvals' over a scratch graph: OUTSIDER -> Actor over
OUTSIDER_ENTRY {approvals: 1}, then Actor -> Privilege over CAN_GRANT or GRANTED.

cost = pathWeight - ENTRY_APPROVALS, so only CAN_GRANT and GRANTED approvals are counted.
The cost is organisation-level structure (§4.5 rule 4). It is returned, never stored on an Actor.
"""

import time
from dataclasses import dataclass, field

from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient
from core.takeover import scratch as sc

COMPUTED = "COMPUTED"
NO_PATH = "NO PATH"
NOT_COMPUTED = "NOT COMPUTED"

ENTRY_APPROVALS = 1
EDGE_TYPES = ("CAN_GRANT", "GRANTED")

PATH_QUERY = (
    "MATCH (s:Flow {id: 'OUTSIDER'}), (t:Privilege {kind: $kind}) "
    "CALL algo.SPpaths({sourceNode: s, targetNode: t, "
    "relTypes: ['OUTSIDER_ENTRY', 'CAN_GRANT', 'GRANTED'], weightProp: 'approvals'}) "
    "YIELD path, pathWeight "
    "RETURN pathWeight, [n IN nodes(path) | coalesce(n.id, n.hid, 'PRIV:' + n.kind)] AS ids "
    "ORDER BY pathWeight LIMIT 1"
)

ENTRY_QUERY = (
    "MERGE (o:Flow {id: 'OUTSIDER'}) "
    "WITH o MATCH (a:Actor) "
    "MERGE (o)-[e:OUTSIDER_ENTRY]->(a) SET e.approvals = $entry"
)


@dataclass
class TakeoverCostResult:
    org: str
    privilege: str
    T: int
    status: str  # COMPUTED, NO PATH or NOT COMPUTED
    cost: int | None = None
    reason: str | None = None
    path: list[str] = field(default_factory=list)
    queries: list[dict] = field(default_factory=list)
    query_ms: float | None = None  # the SPpaths query itself
    provisional: bool = True
    rule: str = sc.RULE


def takeover_cost(
    client: FalkorClient,
    org: str,
    privilege_kind: str,
    T: int,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    run: str | None = None,
) -> TakeoverCostResult:
    T = sc.checked_time(T)
    res = TakeoverCostResult(org=org, privilege=privilege_kind, T=T, status=NOT_COMPUTED)

    exists, rec = sc.privilege_exists(client, org, privilege_kind, timeout_ms)
    res.queries.append(rec.as_dict())
    if not exists:
        res.reason = sc.no_data_reason(org, rec)
        return res

    grants = sc.read_grants(client, org, privilege_kind, T, EDGE_TYPES, timeout_ms)
    res.queries += [q.as_dict() for q in grants.queries]

    with sc.scratch_graph(client, run) as scratch:
        sc.fill_scratch(client, scratch, privilege_kind, grants.rows, timeout_ms)
        client.query(scratch, ENTRY_QUERY, {"entry": ENTRY_APPROVALS}, timeout_ms=timeout_ms)
        params = {"kind": privilege_kind}
        start = time.perf_counter()
        r = client.query(scratch, PATH_QUERY, params, timeout_ms=timeout_ms)
        res.query_ms = (time.perf_counter() - start) * 1000
        res.queries.append(
            sc.QueryRecord("sppaths", PATH_QUERY, params, res.query_ms, len(r.result_set)).as_dict()
        )

    if not r.result_set:
        res.status = NO_PATH
        res.reason = "no path"
        return res
    path_weight, ids = r.result_set[0]
    res.status = COMPUTED
    res.cost = int(round(path_weight)) - ENTRY_APPROVALS
    res.path = list(ids)
    return res
