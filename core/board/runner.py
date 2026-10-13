"""A worker loop over the task board: claim, run the tool under guardrails, log the step, hand in.

Owner: Block F. This is the coordination skeleton the agents plug into (8.2); the executors here are
the deterministic tools only (takeover cost, guardians). No LLM. Findings are whatever the tools
return, stored on the task as canonical JSON in `result_ref`.

Many workers may run this loop at once, over one graph or over many org graphs on one board.
"""

import json
import time
from collections.abc import Callable, Sequence

from core.agents import agent_step
from core.agents import guardrails as gr
from core.board import board
from core.graph.client import FalkorClient
from core.takeover import cost as cost_mod
from core.takeover import guardians as guardians_mod

Executor = Callable[[FalkorClient, str, str, int], dict]  # (client, graph, org, T) -> result


def _takeover_cost(client: FalkorClient, graph: str, org: str, T: int) -> dict:
    r = cost_mod.takeover_cost(client, org, "release", T)
    return {"status": r.status, "cost": r.cost, "path": r.path, "reason": r.reason}


def _guardians(client: FalkorClient, graph: str, org: str, T: int) -> dict:
    r = guardians_mod.guardians(client, org, "release", T)
    return {"status": r.status, "guardians": r.guardians, "reason": r.reason}


def _graph_read(client: FalkorClient, graph: str, org: str, T: int) -> dict:
    """A read that works in any graph, including red-team and harden copies, which the takeover
    tools (they open org_<id>) cannot read."""
    n = client.query(graph, "MATCH (a:Actor) RETURN count(a)", timeout_ms=5000).result_set[0][0]
    e = client.query(graph, "MATCH ()-[r]->() RETURN count(r)", timeout_ms=5000).result_set[0][0]
    return {"actors": n, "edges": e}


EXECUTORS: dict[str, Executor] = {
    "takeover_cost": _takeover_cost,
    "guardians": _guardians,
    "graph_read": _graph_read,
}


def canonical(result: dict) -> str:
    return json.dumps(result, sort_keys=True, separators=(",", ":"))


def now_ms() -> int:
    return int(time.time() * 1000)


def work(
    client: FalkorClient,
    graphs: Sequence[str],
    agent: str,
    *,
    T: int,
    executors: dict[str, Executor] = EXECUTORS,
    breaker: gr.CircuitBreaker | None = None,
    clock: Callable[[], int] = now_ms,
    on_claim: Callable[[str, str], None] | None = None,
    max_tasks: int | None = None,
) -> dict:
    """Claim and finish tasks in `graphs` (tried in the order given) until none can be claimed.
    Returns counts: done, held, stale."""
    breaker = breaker or gr.CircuitBreaker()
    counts = {"done": 0, "held": 0, "stale": 0}
    while max_tasks is None or sum(counts.values()) < max_tasks:
        for graph in graphs:
            task_id = board.claim(client, graph, agent, clock())
            if task_id:
                break
        else:
            return counts
        if on_claim:
            on_claim(graph, task_id)
        task = board.get_task(client, graph, task_id)
        kind, org = task["kind"], board.org_of(graph)
        started = time.perf_counter()

        def run(attempt: int, kind=kind, graph=graph, org=org) -> dict:
            return executors[kind](client, graph, org, T)

        outcome = gr.run_guarded(kind, run, breaker=breaker, now=clock)
        ms = (time.perf_counter() - started) * 1000
        if outcome.held:
            gr.apply_outcome(client, graph, task_id, outcome, agent, clock())
            counts["held"] += 1
            continue
        agent_step.log_step(
            client, graph, task_id, agent, kind, f"run {kind} as of {T}", ms,
            canonical(outcome.result), 0, clock(),
        )  # fmt: skip
        verdict = board.complete(client, graph, task_id, agent, clock(), canonical(outcome.result))
        counts["done" if verdict == board.ACCEPTED else "stale"] += 1
    return counts
