"""make faults (docs/HEARTHGUARD.md 8.4, 10.2): inject every failure type, including "LLM offline",
and check each ends in a bounded HOLD while the structural detectors keep running.

For each failure type a task is claimed on a scratch org board and its plan fails in that way. Where
the failure can be real, it is real: LLM offline is the real LLMClient with no key and an empty
cache; a query timeout is a real 1 ms timeout on a real query; graph unavailable is a real
connection to a closed port; layout mismatch is the real layout check on an empty graph; bad
input is the real takeover tool refused a missing T. The rest (bad output, LLM rate limit, bad LLM
JSON, unnamed tool error) are raised by the test plan, since they need a live model to occur
naturally. Each result says which.

Checks per failure type:
  held           the guarded run returned a HOLD with a named failure type and reason
  bounded        hold_until is exactly now + HOLD_MS; the task is HELD on the board; at the deadline
                 expire_holds sends it to HUMAN_REVIEW; it is never claimed meanwhile
  no_llm_on_abort the LLM client made no call while the HOLD was applied
  structural_ok  takeover cost and guardians still compute the fixture's known answers afterwards

Plus a circuit-breaker scenario (3 holds of one type suspend the plan; the 4th task is not run) and
a mixed board with the LLM offline (LLM tasks HELD, structural tasks DONE).

Usage:  uv run python -m eval.faults
Writes eval/results/faults_run.json. Exit 1 if any check fails. Scratch graphs only.
"""

import json
import tempfile
from pathlib import Path

from pydantic import BaseModel

from core.agents import guardrails as gr
from core.board import board, runner
from core.graph.client import FalkorClient
from core.graph.schema import apply_schema
from core.llm.client import DailyLimitReached, InvalidJSON, LLMClient
from core.takeover import cost as cost_mod
from core.takeover import guardians as guardians_mod
from tests.fixtures.takeover_cases import CASES
from tests.integration.scratch_graphs import drop_owned, new_org_id

OUT = Path(__file__).resolve().parent / "results" / "faults_run.json"
FIXTURE = next(c for c in CASES if c.name == "b_two_keepers")  # cost 1, guardians 2
NOW = 1_700_000_000_000


class Plan(BaseModel):
    n: int


class Reply(BaseModel):
    ok: bool


def offline_llm() -> LLMClient:
    """The real client with no key and an empty cache: every call fails as an offline model does."""
    return LLMClient(key=None, cache_dir=Path(tempfile.mkdtemp()), log=lambda _m: None)


def injectors(client: FalkorClient, org: str, llm: LLMClient):
    """failure type -> (how it is injected, plan(attempt) that fails that way, validate model)."""

    def llm_offline(_a):
        return llm.complete_json(model="m", prompt="plan", schema_model=Reply)

    def timeout(_a):
        client.query(f"org_{org}", "UNWIND range(1, 1000000000) AS x RETURN sum(x)", timeout_ms=1)

    def unavailable(_a):
        FalkorClient(host="127.0.0.1", port=1).query("g", "RETURN 1", timeout_ms=1000)

    def layout(_a):
        gr.check_layout(client, f"org_{org}", {"Privilege", "NoSuchLabel"})

    def bad_input(_a):
        cost_mod.takeover_cost(client, org, "release", None)

    def raise_(exc):
        def f(_a):
            raise exc

        return f

    F = gr.FailureType
    return {
        F.LLM_OFFLINE: ("real: LLMClient with no key", llm_offline, None),
        F.QUERY_TIMEOUT: ("real: 1 ms timeout on a long query", timeout, None),
        F.GRAPH_UNAVAILABLE: ("real: connection to a closed port", unavailable, None),
        F.LAYOUT_MISMATCH: ("real: layout check on a label the graph lacks", layout, None),
        F.TOOL_INPUT_INVALID: ("real: takeover_cost refused T=None", bad_input, None),
        F.TOOL_OUTPUT_INVALID: (
            "injected: plan returns a result that breaks its schema",
            lambda _a: {"n": "not an int"},
            Plan,
        ),
        F.LLM_LIMIT_REACHED: ("injected: DailyLimitReached", raise_(DailyLimitReached("x")), None),
        F.LLM_INVALID_JSON: ("injected: InvalidJSON", raise_(InvalidJSON("x")), None),
        F.TOOL_ERROR: ("injected: unnamed tool error", raise_(RuntimeError("boom")), None),
    }


def structural_ok(client: FalkorClient, org: str) -> bool:
    c = cost_mod.takeover_cost(client, org, "release", FIXTURE.T)
    g = guardians_mod.guardians(client, org, "release", FIXTURE.T)
    return (
        c.status == "COMPUTED"
        and c.cost == FIXTURE.cost
        and g.status == "COMPUTED"
        and g.guardians == FIXTURE.guardians
    )


def new_board(client: FalkorClient):
    oid = new_org_id()
    graph = f"org_{oid}"
    client.drop(graph)
    apply_schema(client, graph)
    FIXTURE.build(client, graph)
    return oid, graph


def circuit_scenario(client: FalkorClient) -> dict:
    oid, graph = new_board(client)
    llm = offline_llm()
    try:
        ran = []

        def plan(_a):
            ran.append(1)
            return llm.complete_json(model="m", prompt="plan", schema_model=Reply)

        breaker = gr.CircuitBreaker()
        reasons = []
        for i in range(4):
            tid = f"t{i}"
            board.add_task(client, graph, tid, "plan", 0, i, synthetic=True)
            board.claim(client, graph, "faults", NOW)
            out = gr.run_guarded("plan", plan, breaker=breaker, now=lambda: NOW)
            gr.apply_outcome(client, graph, tid, out, "faults", NOW)
            reasons.append(str(out.hold_reason))
        statuses = board.tasks_by_status(client, graph)
        res = {
            "hold_reasons": reasons,
            "plan_runs": len(ran),
            "breaker_open": breaker.is_open("plan"),
            "statuses": statuses,
            "llm_calls_made_by_aborted_tasks": len(llm.calls),
            "structural_ok": structural_ok(client, oid),
        }
        res["passed"] = (
            reasons == ["NOT_REPLANNABLE"] * 3 + ["CIRCUIT_OPEN"]
            and res["plan_runs"] == 3
            and res["breaker_open"]
            and statuses == {"HELD": 4}
            and res["structural_ok"]
        )
        return res
    finally:
        drop_owned(client, oid)


def mixed_board_scenario(client: FalkorClient) -> dict:
    """LLM offline: model tasks are HELD, structural tasks finish with the right answer."""
    oid, graph = new_board(client)
    llm = offline_llm()
    try:
        for i in range(3):
            board.add_task(client, graph, f"llm{i}", "llm_plan", 5, i, synthetic=True)
        board.add_task(client, graph, "cost", "takeover_cost", 1, 0, synthetic=True)
        board.add_task(client, graph, "guard", "guardians", 1, 1, synthetic=True)

        def llm_plan(_c, _g, _o, _T):
            return llm.complete_json(model="m", prompt="plan", schema_model=Reply)

        counts = runner.work(
            client, [graph], "faults", T=FIXTURE.T, clock=lambda: NOW,
            executors={**runner.EXECUTORS, "llm_plan": llm_plan},
        )  # fmt: skip
        statuses = {
            t: board.get_task(client, graph, t)["status"]
            for t in ("llm0", "llm1", "llm2", "cost", "guard")
        }
        cost = json.loads(board.get_task(client, graph, "cost")["result_ref"])
        guard = json.loads(board.get_task(client, graph, "guard")["result_ref"])
        res = {
            "counts": counts,
            "statuses": statuses,
            "structural_results": {"cost": cost["cost"], "guardians": guard["guardians"]},
            "llm_calls_that_reached_a_model": sum(1 for c in llm.calls if not c.cache_hit),
        }
        res["passed"] = (
            all(statuses[f"llm{i}"] == board.HELD for i in range(3))
            and statuses["cost"] == statuses["guard"] == board.DONE
            and cost["cost"] == FIXTURE.cost
            and guard["guardians"] == FIXTURE.guardians
        )
        return res
    finally:
        drop_owned(client, oid)


def run() -> dict:
    client = FalkorClient()
    failures = []
    for ft in gr.FailureType:
        # Each failure gets its own board; the injectors are built against that board's org.
        oid, graph = new_board(client)
        try:
            how, plan, validate = injectors(client, oid, offline_llm())[ft]
            failures.append(one_failure(client, oid, graph, ft, how, plan, validate))
        finally:
            drop_owned(client, oid)
    covered = {f["failure_type"] for f in failures}
    result = {
        "failure_types_in_code": sorted(str(f) for f in gr.FailureType),
        "failure_types_injected": sorted(covered),
        "all_types_injected": covered == {str(f) for f in gr.FailureType},
        "failures": failures,
        "circuit_breaker": circuit_scenario(client),
        "mixed_board_llm_offline": mixed_board_scenario(client),
        "limits": {
            "max_replans": gr.MAX_REPLANS,
            "breaker_threshold": gr.BREAKER_THRESHOLD,
            "hold_ms": gr.HOLD_MS,
            "plan_time_limit_ms": gr.PLAN_TIME_LIMIT_MS,
            "note": "hold_ms and plan_time_limit_ms are policy settings, not measurements",
        },
        "synthetic": True,
    }
    result["passed"] = (
        result["all_types_injected"]
        and all(f["passed"] for f in failures)
        and result["circuit_breaker"]["passed"]
        and result["mixed_board_llm_offline"]["passed"]
    )
    return result


def one_failure(client, oid, graph, ft, how, plan, validate) -> dict:
    """one_failure, on a board that already exists (so the injector's org matches the board)."""
    llm = offline_llm()
    board.add_task(client, graph, "t1", "plan", 0, 0, synthetic=True)
    assert board.claim(client, graph, "faults", NOW) == "t1"
    calls_before = len(llm.calls)
    out = gr.run_guarded(
        "plan", plan, breaker=gr.CircuitBreaker(), now=lambda: NOW, validate=validate
    )
    status = gr.apply_outcome(client, graph, "t1", out, "faults", NOW)
    status_in_graph = board.get_task(client, graph, "t1")["status"]
    not_claimable = board.claim(client, graph, "other", out.hold_until - 1) is None
    board.expire_holds(client, graph, out.hold_until)
    final = board.get_task(client, graph, "t1")["status"]
    res = {
        "failure_type": str(ft),
        "how": how,
        "outcome": {
            "status": out.status,
            "hold_reason": str(out.hold_reason),
            "classified_as": str(out.failure_type),
            "replans": out.replans,
            "hold_ms": out.hold_until - NOW if out.hold_until else None,
        },
        "checks": {
            "held": out.held and out.failure_type is not None and status == board.HELD,
            "named_as_injected": out.failure_type == ft,
            "bounded": (
                out.hold_until == NOW + gr.HOLD_MS
                and status_in_graph == board.HELD
                and not_claimable
                and final == board.HUMAN_REVIEW
            ),
            "replans_within_limit": out.replans <= gr.MAX_REPLANS,
            "no_llm_on_abort": len(llm.calls) == calls_before,
            "structural_ok": structural_ok(client, oid),
        },
    }
    res["passed"] = all(res["checks"].values())
    return res


def main() -> int:
    result = run()
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    summary = {
        "passed": result["passed"],
        "all_types_injected": result["all_types_injected"],
        "per_type": {f["failure_type"]: f["passed"] for f in result["failures"]},
        "circuit_breaker": result["circuit_breaker"]["passed"],
        "mixed_board_llm_offline": result["mixed_board_llm_offline"]["passed"],
    }
    print(json.dumps(summary, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
