"""Shared pieces for the detectors (docs/HEARTHGUARD.md §7.1).

A detector is a read-only function of the graph and an as-of time T. It returns a DetectorResult
with a status, a reason, the evidence it used and every query it ran. It never writes to the org
graph, never calls an LLM, and never decides what to do about its result (that is the decision
policy, §7.3, not built here).

Every read goes through the as-of helper or the read-only guard, with an explicit timeout.
"""

import time
from dataclasses import asdict, dataclass, field
from typing import Any

from core.graph.as_of import run_as_of
from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient
from core.graph.ro_guard import MAX_LIMIT, ro_query
from core.takeover import scratch as sc

FIRED = "FIRED"
NOT_FIRED = "NOT_FIRED"
NOT_COMPUTED = "NOT_COMPUTED"

PAGE = MAX_LIMIT


@dataclass
class DetectorResult:
    detector: str
    org: str
    T: int
    status: str
    reason: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    queries: list[dict] = field(default_factory=list)
    query_ms: float | None = None  # total wall-clock time of the queries
    provisional: bool = False
    # Lone keeper only: it is a risk multiplier flag, never a move that fires on its own.
    flag: bool | None = None
    multiplier_only: bool | None = None

    def as_dict(self) -> dict:
        return asdict(self)


class Reader:
    """Runs read-only queries for one detector call and records each one."""

    def __init__(
        self, client: FalkorClient, org: str, T: int, timeout_ms: int = DEFAULT_TIMEOUT_MS
    ):
        self.client = client
        self.graph = sc.graph_for(org)
        self.T = T
        self.timeout_ms = timeout_ms
        self.records: list[sc.QueryRecord] = []

    def add(self, record: sc.QueryRecord) -> None:
        self.records.append(record)

    def _run(self, name: str, runner, cypher: str, params: dict) -> Any:
        start = time.perf_counter()
        result = runner(self.client, self.graph, cypher, params, timeout_ms=self.timeout_ms)
        ms = (time.perf_counter() - start) * 1000
        self.records.append(sc.QueryRecord(name, cypher, params, ms, len(result.result_set)))
        return result

    def as_of(self, name: str, cypher: str, params: dict | None = None) -> Any:
        """A read that must reference $T. T is added to the parameters."""
        return self._run(name, run_as_of, cypher, {**(params or {}), "T": self.T})

    def plain(self, name: str, cypher: str, params: dict | None = None) -> Any:
        """A read of something that carries no time (a node property)."""
        return self._run(name, ro_query, cypher, dict(params or {}))

    def paged(self, name: str, cypher: str, params: dict | None = None) -> list[list]:
        """As-of read, all pages. `cypher` needs a stable ORDER BY and no SKIP or LIMIT."""
        rows: list[list] = []
        skip = 0
        while True:
            r = self.as_of(
                name, f"{cypher} SKIP $skip LIMIT {PAGE}", {**(params or {}), "skip": skip}
            )
            rows += r.result_set
            if len(r.result_set) < PAGE:
                return rows
            skip += PAGE

    def finish(self, res: DetectorResult) -> DetectorResult:
        res.queries = [q.as_dict() for q in self.records]
        res.query_ms = sum(q.ms for q in self.records)
        return res
