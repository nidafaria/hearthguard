"""Scratch graph for takeover cost and guardians (docs/decisions/0001-outsider-edges.md).

The org graph is only read. Grant edges visible at time T are read from it through the as-of
helper and the read-only guard, copied into a scratch graph `takeover_<run>`, and the scratch
graph is dropped when the computation ends, even if it fails. So the org graph never gets a Flow
node, and the exact §7.4 projection runs on data that is already filtered to at <= T.

PROPOSED rule, provisional output: see the decision file.
"""

import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from redis.exceptions import ResponseError

from core.graph.as_of import as_of_fragment, run_as_of, with_as_of
from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient
from core.graph.ro_guard import MAX_LIMIT, ro_query

RULE = "0001-outsider-edges (PROPOSED)"
PAGE = MAX_LIMIT
WRITE_BATCH = 500


@dataclass
class QueryRecord:
    """One query that ran: its text, parameters and wall-clock time."""

    name: str
    query: str
    params: dict[str, Any]
    ms: float
    rows: int | None = None

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "query": self.query,
            "params": self.params,
            "ms": self.ms,
            "rows": self.rows,
        }


@dataclass
class GrantRead:
    rows: list[dict] = field(default_factory=list)
    queries: list[QueryRecord] = field(default_factory=list)


def graph_for(org: str) -> str:
    return f"org_{org}"


def privilege_exists(
    client: FalkorClient, org: str, kind: str, timeout_ms: int = DEFAULT_TIMEOUT_MS
) -> tuple[bool, QueryRecord]:
    """Whether the org graph has a Privilege node of this kind. Nodes carry no time, so no $T."""
    cypher = "MATCH (p:Privilege {kind: $kind}) RETURN count(p) AS n LIMIT 1"
    params = {"kind": kind}
    start = time.perf_counter()
    try:
        r = ro_query(client, graph_for(org), cypher, params, timeout_ms=timeout_ms)
    except ResponseError as e:
        if "empty key" not in str(e):
            raise
        # A read does not create the graph. A missing org graph has no privileges.
        ms = (time.perf_counter() - start) * 1000
        return False, QueryRecord("privilege_exists (graph missing)", cypher, params, ms, None)
    ms = (time.perf_counter() - start) * 1000
    n = r.result_set[0][0]
    return n > 0, QueryRecord("privilege_exists", cypher, params, ms, n)


def read_grants(
    client: FalkorClient,
    org: str,
    kind: str,
    T: int,
    edge_types: tuple[str, ...],
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> GrantRead:
    """Grant edges to Privilege `kind` visible at T: (hid, edge type, approvals). Paged, ordered.

    An edge with `at` counts only if at <= T. An edge with no `at` always counts.
    `approvals_required` (spec §6.1) is read as the approval count, then `approvals`, then 1.
    """
    types = "|".join(edge_types)
    cypher = (
        f"MATCH (a:Actor)-[e:{types}]->(p:Privilege {{kind: $kind}}) "
        f"WHERE (e.at IS NULL OR {as_of_fragment('e')}) "
        "RETURN a.hid AS hid, type(e) AS rel, "
        "coalesce(e.approvals_required, e.approvals, 1) AS approvals "
        f"ORDER BY hid, rel SKIP $skip LIMIT {PAGE}"
    )
    out = GrantRead()
    skip = 0
    while True:
        params = {"kind": kind, "T": T, "skip": skip}
        start = time.perf_counter()
        r = run_as_of(client, graph_for(org), cypher, params, timeout_ms=timeout_ms)
        ms = (time.perf_counter() - start) * 1000
        out.queries.append(QueryRecord("read_grants", cypher, params, ms, len(r.result_set)))
        out.rows += [{"hid": h, "rel": t, "approvals": a} for h, t, a in r.result_set]
        if len(r.result_set) < PAGE:
            return out
        skip += PAGE


@contextmanager
def scratch_graph(client: FalkorClient, run: str | None = None) -> Iterator[str]:
    """Yield a fresh scratch graph name, `takeover_<run>`, and always drop it afterwards."""
    name = f"takeover_{run or uuid.uuid4().hex[:12]}"
    client.drop(name)  # a stale graph with this name would corrupt the result
    try:
        yield name
    finally:
        client.drop(name)


def fill_scratch(
    client: FalkorClient,
    scratch: str,
    kind: str,
    rows: list[dict],
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> None:
    """Write the grant edges into the scratch graph, one relationship type at a time."""
    for rel in sorted({r["rel"] for r in rows}):
        typed = [r for r in rows if r["rel"] == rel]
        for i in range(0, len(typed), WRITE_BATCH):
            client.query(
                scratch,
                "UNWIND $rows AS r "
                "MERGE (a:Actor {hid: r.hid}) "
                "MERGE (p:Privilege {kind: $kind}) "
                f"MERGE (a)-[e:{rel}]->(p) "
                "SET e.approvals = r.approvals",
                {"rows": typed[i : i + WRITE_BATCH], "kind": kind},
                timeout_ms=timeout_ms,
            )


def no_data_reason(org: str, rec: QueryRecord) -> str:
    """Why a computation has nothing to work on. `rows is None` means the org graph is missing."""
    if rec.rows is None:
        return f"org graph {graph_for(org)} does not exist"
    return f"no CAN_GRANT or Privilege data in {graph_for(org)}"


def checked_time(T: Any) -> int:
    """Refuse a missing T before anything touches the server."""
    return with_as_of({}, T)["T"]
