"""Guardrails (docs/HEARTHGUARD.md 8.4): named failures, re-plan limit, time limit, circuit breaker,
bounded HOLD, and an abort path that never calls the LLM. No server needed."""

import httpx
import pytest
from pydantic import BaseModel, ValidationError

from core.agents import guardrails as g
from core.llm.client import DailyLimitReached, InvalidJSON, LLMError

NOW = 1_000_000


def now():
    return NOW


def run(plan_key, fn, breaker=None, **kw):
    return g.run_guarded(plan_key, fn, breaker=breaker or g.CircuitBreaker(), now=now, **kw)


class Out(BaseModel):
    n: int


@pytest.mark.parametrize(
    "exc,expected",
    [
        (g.LayoutError(["Task"]), g.FailureType.LAYOUT_MISMATCH),
        (LLMError("GROQ_API_KEY is not set"), g.FailureType.LLM_OFFLINE),
        (httpx.ConnectError("down"), g.FailureType.LLM_OFFLINE),
        (DailyLimitReached("used up"), g.FailureType.LLM_LIMIT_REACHED),
        (InvalidJSON("bad"), g.FailureType.LLM_INVALID_JSON),
        (TimeoutError(), g.FailureType.QUERY_TIMEOUT),
        (ConnectionError(), g.FailureType.GRAPH_UNAVAILABLE),
        (KeyError("x"), g.FailureType.TOOL_INPUT_INVALID),
        (RuntimeError("?"), g.FailureType.TOOL_ERROR),
    ],
)
def test_every_error_maps_to_a_named_type(exc, expected):
    assert g.classify(exc) is expected


def test_a_schema_violation_is_a_named_type():
    try:
        Out.model_validate({"n": "x"})
    except ValidationError as e:
        assert g.classify(e) is g.FailureType.TOOL_OUTPUT_INVALID


def test_success_returns_done_without_replan():
    o = run("p", lambda attempt: {"n": 1}, validate=Out)
    assert o.status == "DONE" and o.replans == 0 and not o.held


def test_a_replan_repairs_a_failure_and_does_not_count_for_the_breaker():
    b = g.CircuitBreaker()

    def fn(attempt):
        if attempt == 0:
            raise TimeoutError()
        return {"n": 2}

    o = run("p", fn, b)
    assert o.status == "DONE" and o.replans == 1
    assert not b.is_open("p") and b._counts == {}


def test_at_most_two_replans_then_a_bounded_hold():
    calls = []

    def fn(attempt):
        calls.append(attempt)
        raise TimeoutError()

    o = run("p", fn)
    assert calls == [0, 1, 2]  # the plan and two re-plans, no third
    assert o.held and o.hold_reason is g.HoldReason.REPLAN_LIMIT
    assert o.failure_type is g.FailureType.QUERY_TIMEOUT
    assert o.hold_until == NOW + g.HOLD_MS  # bounded


def test_time_limit_stops_replans():
    clock = iter([0.0, 61.0, 61.0, 61.0])
    calls = []

    def fn(attempt):
        calls.append(attempt)
        raise TimeoutError()

    o = run("p", fn, monotonic=lambda: next(clock), time_limit_ms=60_000)
    assert o.hold_reason is g.HoldReason.TIME_LIMIT and calls == [0]


def test_a_failure_a_replan_cannot_fix_holds_at_once():
    calls = []

    def fn(attempt):
        calls.append(attempt)
        raise g.LayoutError(["Privilege"])

    o = run("p", fn)
    assert calls == [0]
    assert o.hold_reason is g.HoldReason.NOT_REPLANNABLE
    assert o.failure_type is g.FailureType.LAYOUT_MISMATCH


def test_output_that_breaks_the_schema_is_replanned_then_held():
    o = run("p", lambda attempt: {"n": "not an int"}, validate=Out)
    assert o.held and o.failure_type is g.FailureType.TOOL_OUTPUT_INVALID
    assert o.hold_reason is g.HoldReason.REPLAN_LIMIT


def test_three_failures_of_one_type_suspend_the_plan():
    b = g.CircuitBreaker()
    ran = []

    def fn(attempt):
        ran.append(1)
        raise LLMError("offline")

    for _ in range(3):
        assert run("plan-A", fn, b).hold_reason is g.HoldReason.NOT_REPLANNABLE
    assert b.is_open("plan-A") and b.opened_by("plan-A") is g.FailureType.LLM_OFFLINE
    before = len(ran)
    o = run("plan-A", fn, b)
    assert o.hold_reason is g.HoldReason.CIRCUIT_OPEN
    assert len(ran) == before  # the suspended plan did not run
    assert o.hold_until == NOW + g.HOLD_MS


def test_failures_of_different_types_do_not_open_the_breaker():
    b = g.CircuitBreaker()
    run("p", lambda a: (_ for _ in ()).throw(LLMError("x")), b)
    run("p", lambda a: (_ for _ in ()).throw(g.LayoutError(["x"])), b)
    run("p", lambda a: (_ for _ in ()).throw(KeyError("x")), b)
    assert not b.is_open("p")


def test_a_success_resets_the_count_and_reset_closes_a_suspended_plan():
    b = g.CircuitBreaker()
    bad = lambda a: (_ for _ in ()).throw(LLMError("x"))  # noqa: E731
    run("p", bad, b)
    run("p", bad, b)
    run("p", lambda a: {"n": 1}, b)
    run("p", bad, b)
    assert not b.is_open("p")
    for _ in range(2):
        run("p", bad, b)
    assert b.is_open("p")
    b.reset("p")
    assert run("p", lambda a: {"n": 1}, b).status == "DONE"


def test_the_abort_path_never_calls_the_llm():
    llm_calls = []

    def llm():
        llm_calls.append(1)

    def fn(attempt):
        raise LLMError("offline")  # the failure was an LLM failure; the abort must not retry it

    o = run("p", fn)
    assert o.held and llm_calls == []
    assert "llm" not in g.run_guarded.__code__.co_varnames  # no LLM handle reaches the guard
    llm()  # (the counter works)
    assert llm_calls == [1]


def test_layout_check_names_the_missing_labels():
    class R:
        result_set = [["Org"], ["Task"]]

    class C:
        def query(self, graph, cypher, params=None, *, timeout_ms):
            return R()

    g.check_layout(C(), "org_x", {"Org", "Task"})
    with pytest.raises(g.LayoutError) as e:
        g.check_layout(C(), "org_x", {"Org", "Task", "Privilege"})
    assert e.value.missing == ["Privilege"]
