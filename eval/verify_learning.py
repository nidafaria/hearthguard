"""verify-learning (docs/HEARTHGUARD.md 10.2): a dismissal, the proposal, the safety rules and the
regression gate, end to end on a real FalkorDB.

Usage:  uv run python -m eval.verify_learning
        (make verify-learning, once the lead wires the target)

Uses a scratch org (synthetic tallowdate rows) and a scratch playbook graph. Both are dropped at
the end. Writes eval/results/learning_verify.json. Exit 1 if any step does not hold.
"""

import dataclasses
import json
import time
import uuid
from pathlib import Path

from core.agents import inbox_graph as ig
from core.agents.cases import CASES, RESULTS, normalize_rows
from core.graph.client import FalkorClient
from core.learning import pipeline as pl
from core.playbook import store as pb

OUT = Path(__file__).resolve().parent / "results" / "learning_verify.json"
REASON = "these are our CI bots: dependabot and renovate"


def main() -> int:
    client = FalkorClient()
    org = f"tst{uuid.uuid4().hex[:10]}"
    case = dataclasses.replace(CASES["tallowdate"], org=org)
    playbook_graph = f"playbook_verify{uuid.uuid4().hex[:10]}"
    steps: dict = {}
    try:
        rows = normalize_rows(CASES["tallowdate"], RESULTS)
        now = int(time.time())
        ig.sync_case(client, case, rows, RESULTS, lambda: now)
        quarter = rows[0]["quarter"]
        steps["dismissal"] = {
            "case": "tallowdate (synthetic)",
            "quarter": quarter,
            "reason": REASON,
        }
        steps["dismissal"]["created"] = ig.record_dismissal(client, case, quarter, REASON, now)

        campaigns, real_rows = pl.load_suite(RESULTS)
        out = pl.learn(REASON, campaigns, real_rows, agreements=1)
        steps["proposal"] = {"attempts": out["attempts"], "template": out["template"]}
        steps["safety"] = out["safety"]
        steps["gate"] = out["gate"]
        steps["end_state"] = {"state": out["state"], "reason": out["state_reason"]}

        stored = pb.record(client, out, now, playbook_graph)
        ig.link_learned(
            client, case, quarter, out["exception_id"], out["state"], out["state_reason"]
        )
        steps["playbook"] = {
            "id": stored["id"],
            "state": stored["state"],
            "agreements": stored["agreements"],
        }
        linked = ig.learned_for(client, case, quarter)
        steps["thread_reads_back"] = linked == {
            "exception_id": out["exception_id"],
            "state": out["state"],
            "state_reason": out["state_reason"],
        }

        # Owner memory on the same org: a later quarter with the same situation is held back.
        held = ig.sync_case(client, case, rows, RESULTS, lambda: now)["remembered"]
        steps["owner_memory_held_back"] = held

        ok = (
            steps["dismissal"]["created"] is True
            and out["state"] in ("Shadow", "Adopted", "Rejected", "Human review")
            and steps["thread_reads_back"]
            and (out["gate"] is None or out["gate"]["baseline_matches_saved"])
        )
        steps["holds"] = bool(ok)
    finally:
        client.drop(case.graph)
        client.drop(playbook_graph)

    result = {
        "org_scratch": True,
        "steps": steps,
        "gate_rule": "worst case: every firing of the proposed move is removed at every point",
        "not_applied": "no exception changes a live decision yet (blockers_E.md, row 66)",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(result, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    state = steps["end_state"]["state"]
    print(
        f"verify-learning: {state} ({steps['gate']['planted_lost']} planted lost) "
        f"holds={steps['holds']} -> {OUT.name}"
    )
    return 0 if steps["holds"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
