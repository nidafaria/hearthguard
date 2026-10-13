"""make concurrency (docs/HEARTHGUARD.md 10.2): throughput and p50/p95 read latency while N orgs,
red-team copies and hardening copies run on one board in parallel.

Per org: one scratch org graph (takeover fixture), one red-team copy and one harden copy made with
GRAPH.COPY, each with tasks on the board. W workers claim across all of them. A separate reader
thread times a plain read on an org graph the whole time. Every number comes from this run on this
machine, with a local FalkorDB container; they are not a claim about any other setup.

Usage:  uv run python -m eval.concurrency [--orgs 4] [--workers 4] [--tasks-per-graph 12]
Writes eval/results/concurrency_run.json. Exit 1 if any task fails to finish. Scratch graphs only.
"""

import argparse
import json
import statistics
import threading
import time
from pathlib import Path

from core.board import board, runner
from core.graph.client import FalkorClient
from core.graph.schema import apply_schema
from tests.fixtures.takeover_cases import CASES
from tests.integration.scratch_graphs import drop_owned, new_org_id

OUT = Path(__file__).resolve().parent / "results" / "concurrency_run.json"
FIXTURE = next(c for c in CASES if c.name == "b_two_keepers")


def pct(values: list[float], q: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]


def run(orgs: int = 4, workers: int = 4, tasks_per_graph: int = 12) -> dict:
    client = FalkorClient()
    ids = [new_org_id() for _ in range(orgs)]
    graphs: list[str] = []
    try:
        for oid in ids:
            g = f"org_{oid}"
            client.drop(g)
            apply_schema(client, g)
            FIXTURE.build(client, g)
            rt, hd = f"redteam_{oid}", f"harden_{oid}"
            client.drop(rt)
            client.drop(hd)
            client.copy(g, rt)
            client.copy(g, hd)
            for graph in (g, rt, hd):
                apply_schema(client, graph)
                graphs.append(graph)
        total = 0
        for graph in graphs:
            for i in range(tasks_per_graph):
                kind = (
                    ("takeover_cost", "guardians")[i % 2]
                    if graph.startswith("org_")
                    else "graph_read"
                )
                board.add_task(client, graph, f"t{i:03d}", kind, i % 3, i, synthetic=True)
                total += 1

        latencies: list[float] = []
        stop = threading.Event()

        def reader() -> None:
            c = FalkorClient()
            while not stop.is_set():
                t0 = time.perf_counter()
                c.query(graphs[0], "MATCH (a:Actor) RETURN count(a)", timeout_ms=5000)
                latencies.append((time.perf_counter() - t0) * 1000)

        counts = [{} for _ in range(workers)]

        def worker(i: int) -> None:
            counts[i] = runner.work(FalkorClient(), graphs, f"w{i}", T=FIXTURE.T)

        rd = threading.Thread(target=reader)
        ws = [threading.Thread(target=worker, args=(i,)) for i in range(workers)]
        t0 = time.perf_counter()
        rd.start()
        for w in ws:
            w.start()
        for w in ws:
            w.join()
        elapsed = time.perf_counter() - t0
        stop.set()
        rd.join()

        done = sum(c.get("done", 0) for c in counts)
        statuses: dict[str, int] = {}
        for graph in graphs:
            for s, n in board.tasks_by_status(client, graph).items():
                statuses[s] = statuses.get(s, 0) + n
        return {
            "orgs": orgs,
            "graphs_on_board": len(graphs),
            "workers": workers,
            "tasks": total,
            "tasks_done": done,
            "statuses": statuses,
            "seconds": round(elapsed, 3),
            "throughput_tasks_per_s": round(done / elapsed, 2) if elapsed else None,
            "read_latency_ms": {
                "samples": len(latencies),
                "p50": round(statistics.median(latencies), 3) if latencies else None,
                "p95": round(pct(latencies, 0.95), 3) if latencies else None,
            },
            "note": "local FalkorDB container, this machine, this run only",
            "synthetic": True,
            "passed": statuses == {"DONE": total} and done == total,
        }
    finally:
        for oid in ids:
            drop_owned(client, oid)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orgs", type=int, default=4)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tasks-per-graph", type=int, default=12)
    a = ap.parse_args()
    result = run(a.orgs, a.workers, a.tasks_per_graph)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
