"""Hardening simulator on fixture graphs (docs/HEARTHGUARD.md section 8.5).

simulate(fixture_name, step) builds the fixture as an org graph, copies it with GRAPH.COPY to
`harden_<run>`, applies ONE step from the fixed menu to the copy only, and reruns takeover cost
and guardians (core/takeover/) before and after. The original graph is never written to after
the copy. Every number returned comes from those runs.

Takeover cost and guardians read `org_<id>` graphs, so the hardened copy is copied once more to a
temporary `org_...` name for measurement. All graphs made here are dropped before returning.
Rule under test is PROPOSED and results are provisional (docs/decisions/0001-outsider-edges.md).
"""

import json
import sys
import uuid
from pathlib import Path

from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient
from core.takeover import cost, guardians
from tests.fixtures.takeover_cases import CASES, PRIV, Case

STEP_ADD_KEEPER = "add_second_keeper"
STEP_TWO_APPROVALS = "require_two_approvals"
STEPS = (STEP_ADD_KEEPER, STEP_TWO_APPROVALS)  # the steps the fixture file uses
STEP_PROVENANCE = "require_provenance_ci"  # spec 8.5 row 2: Normal(usual_path) tightened
MENU = (STEP_ADD_KEEPER, STEP_PROVENANCE, STEP_TWO_APPROVALS)  # the OSS menu, spec 8.5

NEW_KEEPER = "KEEPER2"  # placeholder id for the added keeper (fixture data only)
NEW_KEEPER_APPROVALS = 1  # the new keeper can release on one approval (the plain step)
RESULT_PATH = Path(__file__).resolve().parents[2] / "eval" / "results" / "hardening_fixture.json"

# Three fixtures that already have a route to harden.
DEFAULT_FIXTURES = ("a_single_chain", "b_two_keepers", "c_two_approvals")


def _case(name: str) -> Case:
    for c in CASES:
        if c.name == name:
            return c
    raise KeyError(f"unknown fixture {name!r}")


def counts(client: FalkorClient, graph: str) -> dict:
    """Node and relationship counts of a graph."""
    n = client.query(graph, "MATCH (n) RETURN count(n)", timeout_ms=DEFAULT_TIMEOUT_MS)
    e = client.query(graph, "MATCH ()-[r]->() RETURN count(r)", timeout_ms=DEFAULT_TIMEOUT_MS)
    return {"nodes": n.result_set[0][0], "edges": e.result_set[0][0]}


def _stats(res) -> dict:
    return {
        "nodes_created": res.nodes_created,
        "relationships_created": res.relationships_created,
        "properties_set": res.properties_set,
    }


def apply_step(client: FalkorClient, graph: str, step: str, T: int) -> dict:
    """Apply one menu step to `graph` (the hardening copy). Returns what the query changed."""
    if step == STEP_ADD_KEEPER:
        return _stats(
            client.query(
                graph,
                "MATCH (p:Privilege {kind: $k}) "
                "MERGE (a:Actor {hid: $hid}) ON CREATE SET a.kind = 'human' "
                "MERGE (a)-[e:CAN_GRANT]->(p) "
                "SET e.approvals_required = $ar, e.at = $at",
                {"k": PRIV, "hid": NEW_KEEPER, "ar": NEW_KEEPER_APPROVALS, "at": T},
            )
        )
    if step == STEP_PROVENANCE:
        # Release paths must show CI and provenance. Takeover cost and guardians do not read
        # Normal nodes, so this step is measured by them only as "no change".
        return _stats(
            client.query(
                graph,
                "MATCH (n:Normal {metric: 'usual_path'}) SET n.provenance_required = true",
            )
        )
    if step == STEP_TWO_APPROVALS:
        # Every grant route needs at least two approvals. Edges already at 2 or more are kept.
        return _stats(
            client.query(
                graph,
                "MATCH (:Actor)-[e:CAN_GRANT]->(:Privilege {kind: $k}) "
                "SET e.approvals_required = CASE "
                "WHEN coalesce(e.approvals_required, e.approvals, 1) >= 2 "
                "THEN coalesce(e.approvals_required, e.approvals) ELSE 2 END",
                {"k": PRIV},
            )
        )
    raise ValueError(f"unknown step {step!r}; menu is {MENU}")


def measure(client: FalkorClient, org: str, T: int) -> dict:
    c = cost.takeover_cost(client, org, PRIV, T)
    g = guardians.guardians(client, org, PRIV, T)
    return {
        "cost": c.cost,
        "cost_status": c.status,
        "cost_reason": c.reason,
        "guardians": g.guardians,
        "guardians_status": g.status,
    }


def simulate(fixture_name: str, step: str, client: FalkorClient | None = None) -> dict:
    client = client or FalkorClient()
    case = _case(fixture_name)
    if step not in STEPS:
        raise ValueError(f"unknown step {step!r}; menu is {STEPS}")
    run = uuid.uuid4().hex[:10]
    org = f"hf{run}"  # original graph: org_<org>
    org_after = f"hfa{run}"  # measurement copy of the hardened graph: org_<org_after>
    original, harden, evaluated = f"org_{org}", f"harden_{run}", f"org_{org_after}"
    try:
        for g in (original, harden, evaluated):
            client.drop(g)
        case.build(client, original)
        before_counts = counts(client, original)
        before = measure(client, org, case.T)

        client.copy(original, harden)
        apply_step(client, harden, step, case.T)
        harden_counts = counts(client, harden)
        client.copy(harden, evaluated)
        after = measure(client, org_after, case.T)

        return {
            "fixture": fixture_name,
            "step": step,
            "T": case.T,
            "before": before,
            "after": after,
            "original_counts_before": before_counts,
            "original_counts_after": counts(client, original),
            "hardened_copy_counts": harden_counts,
        }
    finally:
        for g in (original, harden, evaluated):
            client.drop(g)


def run_all(fixtures: tuple[str, ...] = DEFAULT_FIXTURES) -> dict:
    client = FalkorClient()
    rows = [simulate(f, s, client) for f in fixtures for s in STEPS]
    return {
        "spec": "docs/HEARTHGUARD.md section 8.5",
        "rule": "docs/decisions/0001-outsider-edges.md (PROPOSED, provisional)",
        "new_keeper_approvals": NEW_KEEPER_APPROVALS,
        "results": rows,
    }


def _fmt(v) -> str:
    return "none" if v is None else str(v)


def main() -> int:
    out = run_all()
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"{'fixture':<18}{'step':<24}{'cost b->a':<14}guardians b->a")
    for r in out["results"]:
        b, a = r["before"], r["after"]
        cost_s = f"{_fmt(b['cost'])}->{_fmt(a['cost'])}"
        print(
            f"{r['fixture']:<18}{r['step']:<24}{cost_s:<14}"
            f"{_fmt(b['guardians'])}->{_fmt(a['guardians'])}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
