"""Guardrails around an agent's plan (docs/HEARTHGUARD.md 8.4). Plain code, no LLM.

  - Layout check: the graph must hold the labels a plan reads before the plan runs.
  - Named failure types: every error a plan can raise is mapped to one FailureType (classify), so
    nothing falls out as an unnamed exception.
  - Re-plans: at most MAX_REPLANS per task, inside PLAN_TIME_LIMIT_MS.
  - Circuit breaker: BREAKER_THRESHOLD tasks of the same plan ending in a HOLD for the same failure
    type suspend the plan; its later tasks go to human review without running. The breaker lives in
    memory; it is not saved across a restart.
  - Abort path: a bounded HOLD (HOLD_MS) and nothing else. run_guarded takes no LLM object and the
    HOLD code path never calls one.

MAX_REPLANS, BREAKER_THRESHOLD come from the spec. PLAN_TIME_LIMIT_MS and HOLD_MS are policy
settings, not measurements.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError
from redis.exceptions import RedisError, ResponseError

from core.board import board
from core.graph.client import DEFAULT_TIMEOUT_MS, FalkorClient
from core.llm.client import DailyLimitReached, InvalidJSON, LLMError

MAX_REPLANS = 2
BREAKER_THRESHOLD = 3
PLAN_TIME_LIMIT_MS = 60_000
HOLD_MS = 24 * 60 * 60 * 1000


class FailureType(StrEnum):
    LAYOUT_MISMATCH = "LAYOUT_MISMATCH"
    TOOL_INPUT_INVALID = "TOOL_INPUT_INVALID"
    TOOL_OUTPUT_INVALID = "TOOL_OUTPUT_INVALID"
    QUERY_TIMEOUT = "QUERY_TIMEOUT"
    GRAPH_UNAVAILABLE = "GRAPH_UNAVAILABLE"
    LLM_OFFLINE = "LLM_OFFLINE"
    LLM_LIMIT_REACHED = "LLM_LIMIT_REACHED"
    LLM_INVALID_JSON = "LLM_INVALID_JSON"
    TOOL_ERROR = "TOOL_ERROR"


# A re-plan asks for a different plan. It cannot help when the cause is the layout, the input, or a
# model that is offline or out of quota (a re-plan needs the model).
REPLANNABLE = frozenset(
    {
        FailureType.TOOL_OUTPUT_INVALID,
        FailureType.QUERY_TIMEOUT,
        FailureType.LLM_INVALID_JSON,
        FailureType.TOOL_ERROR,
    }
)


class HoldReason(StrEnum):
    NOT_REPLANNABLE = "NOT_REPLANNABLE"
    REPLAN_LIMIT = "REPLAN_LIMIT"
    TIME_LIMIT = "TIME_LIMIT"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"


class ToolFailure(Exception):
    """A tool failing in a named way."""

    def __init__(self, failure_type: FailureType, detail: str = "") -> None:
        super().__init__(f"{failure_type}: {detail}" if detail else str(failure_type))
        self.failure_type = failure_type


class LayoutError(ToolFailure):
    def __init__(self, missing: list[str]) -> None:
        super().__init__(FailureType.LAYOUT_MISMATCH, f"missing labels {missing}")
        self.missing = missing


def check_layout(
    client: FalkorClient,
    graph: str,
    required_labels: set[str] | frozenset[str],
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> None:
    """Raise LayoutError unless every label the plan reads exists in `graph`."""
    r = client.query(graph, "CALL db.labels() YIELD label RETURN label", timeout_ms=timeout_ms)
    missing = sorted(set(required_labels) - {row[0] for row in r.result_set})
    if missing:
        raise LayoutError(missing)


def classify(exc: BaseException) -> FailureType:
    if isinstance(exc, ToolFailure):
        return exc.failure_type
    if isinstance(exc, ValidationError):
        return FailureType.TOOL_OUTPUT_INVALID
    if isinstance(exc, DailyLimitReached):
        return FailureType.LLM_LIMIT_REACHED
    if isinstance(exc, InvalidJSON):
        return FailureType.LLM_INVALID_JSON
    if isinstance(exc, (LLMError, httpx.TransportError)):
        return FailureType.LLM_OFFLINE  # no key, network down, or the endpoint refusing
    if isinstance(exc, TimeoutError) or (
        isinstance(exc, ResponseError) and "timed out" in str(exc).lower()
    ):
        return FailureType.QUERY_TIMEOUT
    if isinstance(exc, (ConnectionError, RedisError)):
        return FailureType.GRAPH_UNAVAILABLE
    if isinstance(exc, (TypeError, ValueError, KeyError)):
        return FailureType.TOOL_INPUT_INVALID
    return FailureType.TOOL_ERROR


class CircuitBreaker:
    """Counts consecutive failures of one type per plan. At the threshold the plan is suspended."""

    def __init__(self, threshold: int = BREAKER_THRESHOLD) -> None:
        self.threshold = threshold
        self._counts: dict[tuple[str, FailureType], int] = {}
        self._open: dict[str, FailureType] = {}

    def record_failure(self, plan_key: str, failure_type: FailureType) -> bool:
        """True if this failure opened (or found open) the breaker."""
        k = (plan_key, failure_type)
        self._counts[k] = self._counts.get(k, 0) + 1
        if self._counts[k] >= self.threshold:
            self._open[plan_key] = failure_type
        return self.is_open(plan_key)

    def record_success(self, plan_key: str) -> None:
        if plan_key in self._open:
            return  # a suspended plan stays suspended until reset()
        for k in [k for k in self._counts if k[0] == plan_key]:
            del self._counts[k]

    def is_open(self, plan_key: str) -> bool:
        return plan_key in self._open

    def opened_by(self, plan_key: str) -> FailureType | None:
        return self._open.get(plan_key)

    def reset(self, plan_key: str) -> None:
        self._open.pop(plan_key, None)
        for k in [k for k in self._counts if k[0] == plan_key]:
            del self._counts[k]


@dataclass
class Outcome:
    status: str  # DONE or HOLD
    result: Any = None
    hold_reason: HoldReason | None = None
    failure_type: FailureType | None = None
    detail: str = ""
    replans: int = 0
    failures: list[FailureType] = field(default_factory=list)
    hold_until: int | None = None

    @property
    def held(self) -> bool:
        return self.status == "HOLD"


def run_guarded(
    plan_key: str,
    run: Callable[[int], Any],
    *,
    breaker: CircuitBreaker,
    now: Callable[[], int],
    validate: type[BaseModel] | None = None,
    max_replans: int = MAX_REPLANS,
    time_limit_ms: int = PLAN_TIME_LIMIT_MS,
    hold_ms: int = HOLD_MS,
    monotonic: Callable[[], float] = time.monotonic,
) -> Outcome:
    """Run `run(attempt)`; attempt 0 is the plan, attempts 1.. are re-plans. A failure is named,
    counted by the breaker, and either re-planned (inside the limits) or ends in a bounded HOLD.

    `now` is epoch milliseconds, used for the hold deadline. If `validate` is given, the result
    must fit that Pydantic model or it counts as TOOL_OUTPUT_INVALID.
    """
    out = Outcome(status="HOLD")

    def hold(reason: HoldReason, ft: FailureType | None, detail: str) -> Outcome:
        out.hold_reason, out.failure_type, out.detail = reason, ft, detail
        out.hold_until = now() + hold_ms
        return out

    if breaker.is_open(plan_key):
        return hold(HoldReason.CIRCUIT_OPEN, breaker.opened_by(plan_key), "plan suspended")

    started = monotonic()
    attempt = 0
    while True:
        try:
            result = run(attempt)
            if validate is not None:
                validate.model_validate(result)
            breaker.record_success(plan_key)
            out.status, out.result, out.replans = "DONE", result, attempt
            return out
        except Exception as exc:  # noqa: BLE001 - every error must end in a named failure type
            ft = classify(exc)
            out.failures.append(ft)
            # A failure counts for the breaker when the task ends in a HOLD, not when a re-plan
            # repairs it.
            reason = None
            if ft not in REPLANNABLE:
                reason = HoldReason.NOT_REPLANNABLE
            elif attempt >= max_replans:
                reason = HoldReason.REPLAN_LIMIT
            elif (monotonic() - started) * 1000 >= time_limit_ms:
                reason = HoldReason.TIME_LIMIT
            if reason is not None:
                breaker.record_failure(plan_key, ft)
                return hold(reason, ft, str(exc))
            attempt += 1
            out.replans = attempt


def apply_outcome(
    client: FalkorClient,
    graph: str,
    task_id: str,
    outcome: Outcome,
    agent: str,
    now: int,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> str:
    """Put a HOLD on the board and log it. DONE outcomes are handed in with board.complete by the
    caller. Returns the task status afterwards."""
    from core.agents import agent_step

    if not outcome.held:
        return board.DONE
    board.hold(
        client,
        graph,
        task_id,
        outcome.hold_reason,
        outcome.failure_type or "",
        outcome.hold_until,
        timeout_ms=timeout_ms,
    )
    agent_step.log_step(
        client,
        graph,
        task_id,
        agent,
        "guardrails.hold",
        f"{outcome.hold_reason}: {outcome.detail}"[:300],
        0,
        None,
        0,
        now,
        timeout_ms=timeout_ms,
    )
    return board.HELD
