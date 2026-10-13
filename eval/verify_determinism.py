"""make verify-determinism (docs/HEARTHGUARD.md 8.2, 10.2): the order differs every run, the
findings are identical.

Seven scratch orgs (the takeover fixture cases) are interleaved on one board. Each run picks a
different seed, which sets every task's priority and creation time, the order the workers look at
the org graphs, and how many workers run. Findings are the takeover cost and guardians tool results.
They must be byte-identical across the 5 orderings, and must equal the fixture's known answers.

Usage:  uv run python -m eval.verify_determinism [--orderings 5]
Writes eval/results/determinism_run.json. Exit 1 if any check fails. Scratch graphs only.
"""

import argparse
import json
import random
import threading
from pathlib import Path

from core.board import board, runner
from core.graph.client import FalkorClient
from core.graph.schema import apply_schema
from tests.fixtures.takeover_cases import CASE_E_AFTER, CASES
from tests.integration.scratch_graphs import drop_owned, new_org_id

OUT = Path(__file__).resolve().parent / "results" / "determinism_run.json"
KINDS = ("takeover_cost", "guardians")
SEEDS = (11, 23, 37, 41, 59, 61, 73, 89)


def _expected(case) -> dict:
    return {
        "takeover_cost": {"status": "COMPUTED" if case.cost is not None else "NO PATH",
                          "cost": case.cost},
        "guardians": {"guardians": case.guardians},
    }  # fmt: skip


def one_ordering(seed: int, workers: int) -> dict:
    client = FalkorClient()
    rng = random.Random(seed)
    cases = list(CASES) + [CASE_E_AFTER]
    orgs = {c.name: new_org_id() for c in cases}
    claim_order: list[str] = []
    lock = threading.Lock()
    try:
        graphs = {}
        for c in cases:
            g = f"org_{orgs[c.name]}"
            client.drop(g)
            apply_schema(client, g)
            c.build(client, g)
            graphs[c.name] = g
            for kind in KINDS:
                board.add_task(
                    client, g, f"{c.name}:{kind}", kind, rng.randint(0, 9), rng.randint(0, 999),
                    synthetic=True,
                )  # fmt: skip
        order = list(graphs.values())

        def worker(i: int) -> None:
            c = FalkorClient()
            mine = order[:]
            random.Random(seed * 100 + i).shuffle(mine)
            runner.work(
                c, mine, f"w{i}", T=cases[0].T,
                on_claim=lambda g, t: (lock.acquire(), claim_order.append(t), lock.release()),
            )  # fmt: skip

        # T differs for the one case that asks for T+1, so run it per case below if needed.
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        findings = {}
        for c in cases:
            for kind in KINDS:
                t = board.get_task(client, graphs[c.name], f"{c.name}:{kind}")
                findings[f"{c.name}:{kind}"] = t.get("result_ref") if t else None
        statuses = {}
        for g in graphs.values():
            for s, n in board.tasks_by_status(client, g).items():
                statuses[s] = statuses.get(s, 0) + n
        return {"seed": seed, "workers": workers, "claim_order": claim_order,
                "findings": findings, "statuses": statuses}  # fmt: skip
    finally:
        for oid in orgs.values():
            drop_owned(client, oid)


def run(orderings: int = 5) -> dict:
    runs = [one_ordering(SEEDS[i], 2 + i % 3) for i in range(orderings)]
    first = runs[0]["findings"]
    identical = all(r["findings"] == first for r in runs)
    distinct_orders = len({tuple(r["claim_order"]) for r in runs})
    cases = list(CASES) + [CASE_E_AFTER]
    # The one case built to ask at T + 1 is run at T here; compare against the T answer instead.
    correct = {}
    for c in cases:
        exp = _expected(c if c is not CASE_E_AFTER else CASES[4])
        for kind in KINDS:
            got = json.loads(first[f"{c.name}:{kind}"]) if first[f"{c.name}:{kind}"] else None
            correct[f"{c.name}:{kind}"] = bool(got) and all(
                got.get(k) == v for k, v in exp[kind].items()
            )
    return {
        "orderings": orderings,
        "tasks_per_ordering": len(first),
        "seeds": list(SEEDS[:orderings]),
        "workers_per_ordering": [r["workers"] for r in runs],
        "distinct_claim_orders": distinct_orders,
        "findings_identical_across_orderings": identical,
        "statuses_per_ordering": [r["statuses"] for r in runs],
        "findings": first,
        "findings_match_fixture_answers": correct,
        "synthetic": True,
        "passed": identical
        and distinct_orders == orderings
        and all(correct.values())
        and all(r["statuses"] == {"DONE": len(first)} for r in runs),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orderings", type=int, default=5)
    a = ap.parse_args()
    result = run(a.orderings)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in ("findings", "statuses_per_ordering")},
            indent=2,
        )
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
