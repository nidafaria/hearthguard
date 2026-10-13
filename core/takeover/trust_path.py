"""Trust path from a young actor to a sensitive privilege (docs/HEARTHGUARD.md §7.6).

The spec's query, run on a scratch graph that holds only facts visible at T:

    MATCH (a:Actor {hid:$hid}), (k:Privilege {kind:$privilege})
    CALL algo.SPpaths({sourceNode:a, targetNode:k,
                       relTypes:['VOUCHED_FOR','REVIEWED','GRANTED'], weightProp:'w'})
    YIELD path, pathWeight RETURN path, pathWeight

Edge direction (decision 0008): trust flows toward the holder of the power.
  (voucher)-[:VOUCHED_FOR {w:1}]->(candidate)   from a VOUCH claim whose target_hid is the candidate
  (reviewer)-[:REVIEWED   {w:1}]->(author)      from a REVIEWED edge, if the org graph has any
  (holder)  -[:GRANTED    {w:1}]->(Privilege)   from the org's GRANTED edges
Every hop weighs 1, so the path weight is the number of hops. A 2 means "this actor vouched for
someone who holds the privilege".

NO PATH is a result, not an error (spec §1: "no path found" is a real result). The org graph is only
read; the scratch graph is dropped afterwards. No LLM. It returns a structural path, never a score
or a verdict about a person (§4.4).
"""

import time
from dataclasses import dataclass, field

from core.graph.as_of import run_as_of
from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient
from core.graph.ro_guard import MAX_LIMIT
from core.takeover import scratch as sc

COMPUTED = "COMPUTED"
NO_PATH = "NO PATH"
NOT_COMPUTED = "NOT COMPUTED"

REL_TYPES = ("VOUCHED_FOR", "REVIEWED", "GRANTED")

PATH_QUERY = (
    "MATCH (a:Actor {hid: $hid}), (k:Privilege {kind: $privilege}) "
    "CALL algo.SPpaths({sourceNode: a, targetNode: k, "
    "relTypes: ['VOUCHED_FOR', 'REVIEWED', 'GRANTED'], weightProp: 'w'}) "
    "YIELD path, pathWeight "
    "RETURN pathWeight, [n IN nodes(path) | coalesce(n.hid, 'PRIV:' + n.kind)] AS ids, "
    "[r IN relationships(path) | type(r)] AS rels "
    "ORDER BY pathWeight LIMIT 1"
)

VOUCH_QUERY = (
    "MATCH (v:Actor)-[:ASSERTED]->(c:Claim {kind: 'VOUCH'}) "
    "WHERE c.target_hid IS NOT NULL AND c.at <= $T "
    "RETURN DISTINCT v.hid AS src, c.target_hid AS dst ORDER BY src, dst "
    f"SKIP $skip LIMIT {MAX_LIMIT}"
)
REVIEWED_QUERY = (
    "MATCH (r:Actor)-[e:REVIEWED]->(x:Actor) WHERE e.at IS NULL OR e.at <= $T "
    "RETURN DISTINCT r.hid AS src, x.hid AS dst ORDER BY src, dst "
    f"SKIP $skip LIMIT {MAX_LIMIT}"
)


@dataclass
class TrustPathResult:
    org: str
    actor_hid: str
    privilege: str
    T: int
    status: str  # COMPUTED, NO PATH or NOT COMPUTED
    weight: int | None = None
    path: list[str] = field(default_factory=list)  # hashed ids, then 'PRIV:<kind>'
    hops: list[str] = field(default_factory=list)  # the relationship type of each hop
    reason: str | None = None
    queries: list[dict] = field(default_factory=list)
    query_ms: float | None = None  # the SPpaths query itself
    edges_read: dict = field(default_factory=dict)


def _paged(client, org, name, cypher, T, timeout_ms, queries) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    skip = 0
    while True:
        params = {"T": T, "skip": skip}
        start = time.perf_counter()
        r = run_as_of(client, sc.graph_for(org), cypher, params, timeout_ms=timeout_ms)
        queries.append(
            sc.QueryRecord(
                name, cypher, params, (time.perf_counter() - start) * 1000, len(r.result_set)
            ).as_dict()
        )
        rows += [(s, d) for s, d in r.result_set]
        if len(r.result_set) < MAX_LIMIT:
            return rows
        skip += MAX_LIMIT


def trust_path(
    client: FalkorClient,
    org: str,
    actor_hid: str,
    privilege_kind: str,
    T: int,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    run: str | None = None,
) -> TrustPathResult:
    T = sc.checked_time(T)
    res = TrustPathResult(org, actor_hid, privilege_kind, T, NOT_COMPUTED)

    exists, rec = sc.privilege_exists(client, org, privilege_kind, timeout_ms)
    res.queries.append(rec.as_dict())
    if not exists:
        res.reason = sc.no_data_reason(org, rec)
        return res

    vouched = _paged(client, org, "read_vouches", VOUCH_QUERY, T, timeout_ms, res.queries)
    reviewed = _paged(client, org, "read_reviews", REVIEWED_QUERY, T, timeout_ms, res.queries)
    grants = sc.read_grants(client, org, privilege_kind, T, ("GRANTED",), timeout_ms)
    res.queries += [q.as_dict() for q in grants.queries]
    res.edges_read = {
        "VOUCHED_FOR": len(vouched),
        "REVIEWED": len(reviewed),
        "GRANTED": len(grants.rows),
    }

    with sc.scratch_graph(client, run) as scratch:
        for rel, pairs in (("VOUCHED_FOR", vouched), ("REVIEWED", reviewed)):
            if pairs:
                client.query(
                    scratch,
                    "UNWIND $rows AS r MERGE (a:Actor {hid: r.src}) MERGE (b:Actor {hid: r.dst}) "
                    f"MERGE (a)-[e:{rel}]->(b) SET e.w = 1",
                    {"rows": [{"src": s, "dst": d} for s, d in pairs]},
                    timeout_ms=timeout_ms,
                )
        client.query(
            scratch,
            "UNWIND $rows AS r MERGE (a:Actor {hid: r.hid}) MERGE (p:Privilege {kind: $kind}) "
            "MERGE (a)-[e:GRANTED]->(p) SET e.w = 1",
            {"rows": [{"hid": g["hid"]} for g in grants.rows], "kind": privilege_kind},
            timeout_ms=timeout_ms,
        )
        client.query(
            scratch, "MERGE (a:Actor {hid: $hid})", {"hid": actor_hid}, timeout_ms=timeout_ms
        )
        params = {"hid": actor_hid, "privilege": privilege_kind}
        start = time.perf_counter()
        r = client.query(scratch, PATH_QUERY, params, timeout_ms=timeout_ms)
        res.query_ms = (time.perf_counter() - start) * 1000
        res.queries.append(
            sc.QueryRecord("sppaths", PATH_QUERY, params, res.query_ms, len(r.result_set)).as_dict()
        )

    if not r.result_set:
        res.status = NO_PATH
        res.reason = "no trust path from this actor to the privilege"
        return res
    weight, ids, rels = r.result_set[0]
    res.status = COMPUTED
    res.weight = int(round(weight))
    res.path = list(ids)
    res.hops = list(rels)
    return res
