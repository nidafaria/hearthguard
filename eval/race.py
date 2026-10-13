"""make race (docs/HEARTHGUARD.md 10.2): concurrent claims and concurrent note sends on a real
FalkorDB. Claims: no task is claimed by two workers. Notes: zero duplicates, however many writers
race for the same note key. AgentStep numbers: unique under concurrent logging.

Usage:  uv run python -m eval.race [--workers 8] [--tasks 200] [--findings 40]
Scratch graph only (name holds a test id), dropped at the end. Writes eval/results/race_run.json.
Exit 1 if any check fails.
"""

import argparse
import json
import threading
import time
from collections import Counter
from pathlib import Path

from core.agents import agent_step
from core.board import board
from core.graph.client import FalkorClient
from core.graph.schema import apply_schema
from tests.integration.scratch_graphs import drop_owned, new_org_id

OUT = Path(__file__).resolve().parent / "results" / "race_run.json"
BIG_NOW = 10**12  # leases never expire inside this run


def _threads(n: int, fn) -> list:
    errors: list = []

    def wrap(i: int) -> None:
        try:
            fn(i)
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))

    ts = [threading.Thread(target=wrap, args=(i,)) for i in range(n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return errors


def run(workers: int = 8, tasks: int = 200, findings: int = 40) -> dict:
    root = FalkorClient()
    oid = new_org_id()
    graph = f"org_{oid}"
    root.drop(graph)
    apply_schema(root, graph)
    started = time.time()
    try:
        # 1. claims
        for i in range(tasks):
            board.add_task(root, graph, f"t{i:04d}", "race", i % 5, i, synthetic=True)
        claimed: list[list[str]] = [[] for _ in range(workers)]

        def claimer(i: int) -> None:
            c = FalkorClient()
            while True:
                tid = board.claim(c, graph, f"w{i}", BIG_NOW)
                if tid is None:
                    return
                claimed[i].append(tid)
                assert board.complete(c, graph, tid, f"w{i}", BIG_NOW) == board.ACCEPTED

        claim_errors = _threads(workers, claimer)
        all_claims = [t for per in claimed for t in per]
        dup_claims = [t for t, n in Counter(all_claims).items() if n > 1]
        statuses = board.tasks_by_status(root, graph)

        # 2. notes: every worker tries to send every note
        for f in range(findings):
            root.query(graph, "CREATE (:Finding {id: $id, status: 'open'})", {"id": f"f{f}"})
        sends = [0] * workers

        def sender(i: int) -> None:
            c = FalkorClient()
            for f in range(findings):
                if board.send_note(c, graph, f"f{f}", "owner", now=i):
                    sends[i] += 1

        note_errors = _threads(workers, sender)
        notes = root.query(graph, "MATCH (n:Note) RETURN count(n)").result_set[0][0]
        distinct = root.query(graph, "MATCH (n:Note) RETURN count(DISTINCT n.id)").result_set[0][0]

        # 3. AgentStep numbering
        board.add_task(root, graph, "steps", "race", 0, 0, synthetic=True)
        per_worker = 10

        def stepper(i: int) -> None:
            c = FalkorClient()
            for k in range(per_worker):
                agent_step.log_step(c, graph, "steps", f"w{i}", "tool", "race", 0.0, None, 0, k)

        step_errors = _threads(workers, stepper)
        seqs = sorted(s["seq"] for s in agent_step.steps_for(root, graph, "steps"))

        result = {
            "workers": workers,
            "tasks": tasks,
            "findings": findings,
            "claims": {
                "claimed_total": len(all_claims),
                "duplicate_claims": len(dup_claims),
                "statuses": statuses,
                "errors": claim_errors,
            },
            "notes": {
                "notes_in_graph": notes,
                "distinct_note_ids": distinct,
                "sends_reported_true": sum(sends),
                "expected": findings,
                "errors": note_errors,
            },
            "agent_steps": {
                "expected": workers * per_worker,
                "seqs_unique_and_contiguous": seqs == list(range(workers * per_worker)),
                "errors": step_errors,
            },
            "seconds": round(time.time() - started, 2),
            "synthetic": True,
        }
        result["passed"] = (
            result["claims"]["duplicate_claims"] == 0
            and result["claims"]["claimed_total"] == tasks
            and statuses.get("DONE") == tasks
            and notes == findings == distinct == sum(sends)
            and result["agent_steps"]["seqs_unique_and_contiguous"]
            and not (claim_errors or note_errors or step_errors)
        )
        return result
    finally:
        drop_owned(root, oid)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--tasks", type=int, default=200)
    ap.add_argument("--findings", type=int, default=40)
    a = ap.parse_args()
    result = run(a.workers, a.tasks, a.findings)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps({k: result[k] for k in ("claims", "notes", "agent_steps", "passed")}, indent=2)
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
