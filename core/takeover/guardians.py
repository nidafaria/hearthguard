"""Guardians (docs/HEARTHGUARD.md §7.4): the fewest people on every route from an outsider.

The minimum vertex cut, from algo.maxFlow on the node-split projection. Each person is split into
in -> out with capacity 1, every other edge has a large capacity, all as the single relationship
type CAP. The projection and the guardians query below are the §7.4 Cypher, character for
character apart from comments and layout (tests/integration/test_takeover.py compares them to
the spec text).

PROPOSED rule, provisional output (docs/decisions/0001-outsider-edges.md). The projection reads
CAN_GRANT only, as the spec does. The result is organisation-level structure (§4.5 rule 4). It is
returned, never stored on an Actor.
"""

import time
from dataclasses import dataclass, field

from redis.exceptions import ResponseError

from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient
from core.takeover import scratch as sc

COMPUTED = "COMPUTED"
NOT_COMPUTED = "NOT COMPUTED"

# Spec §7.4, "Projection". Do not edit without changing the spec first.
PROJECTION = """
MATCH (k:Actor)-[:CAN_GRANT]->(p:Privilege {kind:$privilege})
MERGE (ki:Flow {id: k.hid + ':in'})  MERGE (ko:Flow {id: k.hid + ':out'})
MERGE (ki)-[:CAP {c: 1}]->(ko)
MERGE (src:Flow {id:'OUTSIDER'})     MERGE (dst:Flow {id:'PRIV:' + $privilege})
MERGE (src)-[:CAP {c: 1000000}]->(ki)
MERGE (ko)-[:CAP {c: 1000000}]->(dst);
"""

# Spec §7.4, "Guardians".
GUARDIANS_QUERY = """
MATCH (s:Flow {id:'OUTSIDER'}), (t:Flow {id:'PRIV:' + $privilege})
CALL algo.maxFlow({sourceNodes:[s], targetNodes:[t], capacityProperty:'c', relationshipTypes:['CAP']})
YIELD maxFlow
RETURN maxFlow AS guardians
"""  # noqa: E501 (the spec line is one line, kept verbatim)


@dataclass
class GuardiansResult:
    org: str
    privilege: str
    T: int
    status: str  # COMPUTED or NOT COMPUTED
    guardians: int | None = None
    reason: str | None = None
    queries: list[dict] = field(default_factory=list)
    query_ms: float | None = None  # the maxFlow query itself
    provisional: bool = True
    rule: str = sc.RULE


def guardians(
    client: FalkorClient,
    org: str,
    privilege_kind: str,
    T: int,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    run: str | None = None,
) -> GuardiansResult:
    T = sc.checked_time(T)
    res = GuardiansResult(org=org, privilege=privilege_kind, T=T, status=NOT_COMPUTED)

    exists, rec = sc.privilege_exists(client, org, privilege_kind, timeout_ms)
    res.queries.append(rec.as_dict())
    if not exists:
        res.reason = sc.no_data_reason(org, rec)
        return res

    grants = sc.read_grants(client, org, privilege_kind, T, ("CAN_GRANT",), timeout_ms)
    res.queries += [q.as_dict() for q in grants.queries]

    params = {"privilege": privilege_kind}
    with sc.scratch_graph(client, run) as scratch:
        sc.fill_scratch(client, scratch, privilege_kind, grants.rows, timeout_ms)
        client.query(scratch, PROJECTION, params, timeout_ms=timeout_ms)
        res.queries.append(sc.QueryRecord("projection", PROJECTION, params, 0.0).as_dict())
        start = time.perf_counter()
        r = client.query(scratch, GUARDIANS_QUERY, params, timeout_ms=timeout_ms)
        res.query_ms = (time.perf_counter() - start) * 1000
        res.queries.append(
            sc.QueryRecord(
                "maxflow", GUARDIANS_QUERY, params, res.query_ms, len(r.result_set)
            ).as_dict()
        )

    res.status = COMPUTED
    if not r.result_set:
        # No keeper can grant the privilege at T, so the projection built no OUTSIDER node.
        res.guardians = 0
        res.reason = "no route from OUTSIDER"
    else:
        res.guardians = int(r.result_set[0][0])
    return res

